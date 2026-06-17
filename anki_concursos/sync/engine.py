import logging
from datetime import datetime, timezone
from typing import Callable, List, Dict

from aqt import mw
from aqt.operations import QueryOp

from ..api.client import ApiClient
from ..storage.database import DatabaseManager
from ..storage.models import RemoteDeck, RemoteCard, SyncLogEntry
from ..services.note_type_manager import NoteTypeManager
from ..services.note_manager import NoteManager
from .backup import BackupManager

logger = logging.getLogger("anki_concursos.sync.engine")

class SyncEngine:
    def __init__(self, api: ApiClient, db: DatabaseManager):
        self.api = api
        self.db = db
        self.nt_manager = NoteTypeManager()
        self.note_manager = NoteManager()
        self.backup_manager = BackupManager(db.db_path)

    def sync_all(self, callback: Callable[[bool, str], None]) -> None:
        """Sync all installed decks incrementally."""
        decks = self.db.get_all_decks()
        if not decks:
            callback(True, "No installed decks to sync.")
            return
            
        def background_job() -> List[dict]:
            # 1. Check version compatibility first
            status = self.api.get_addon_status()
            min_ver = status.get("min_addon_version")
            if min_ver:
                from ..consts import VERSION
                try:
                    curr_parts = [int(p) for p in VERSION.split(".")]
                    req_parts = [int(p) for p in min_ver.split(".")]
                    if curr_parts < req_parts:
                        raise ValueError(f"Sua versão do add-on ({VERSION}) é obsoleta. A versão mínima suportada é {min_ver}. Por favor, atualize o add-on.")
                except ValueError as ve:
                    raise ve
                except Exception:
                    pass # Ignore parsing errors of unexpected version formats
            
            # Fetch updates for all decks
            results = []
            for deck in decks:
                manifest = self.api.get_deck_manifest(deck.deck_id)
                sync_resp = self.api.sync_deck_all_pages(deck.deck_id, since_release=deck.latest_release)
                results.append({"deck": deck, "manifest": manifest, "sync": sync_resp})
            return results
            
        def on_success(results: List[dict]) -> None:
            # We are back on the main thread
            
            # Count total changes
            total_changes = sum(len(r["sync"].changes) for r in results)
            if total_changes == 0:
                callback(True, "Already up to date.")
                return
                
            mw.progress.start(label=f"Applying {total_changes} updates...", immediate=True)
            
            # Create backup before applying
            backup_path = self.backup_manager.create_backup()
            
            try:
                for res in results:
                    self._apply_deck_sync(res["deck"], res["manifest"], res["sync"])
                    
                mw.progress.finish()
                callback(True, f"Successfully synced {total_changes} changes.")
                
            except Exception as e:
                mw.progress.finish()
                logger.exception("Sync failed during application")
                # Attempt to rollback DB
                self.backup_manager.restore_backup(backup_path)
                callback(False, f"Sync failed: {str(e)}. Local database was rolled back. You may need to use Anki's Undo if cards were modified.")
                
        op = QueryOp(
            parent=mw,
            op=lambda _: background_job(),
            success=on_success
        )
        op.failure(lambda exc: callback(False, str(exc)))
        op.with_progress("Checking for updates...").run_in_background()

    def _apply_deck_sync(self, deck: RemoteDeck, manifest, sync_resp) -> None:
        if not sync_resp.has_changes or not sync_resp.changes:
            return
            
        now = datetime.now(timezone.utc).isoformat()
        stats = {"added": 0, "updated": 0, "removed": 0, "deprecated": 0}
        
        # Ensure note types
        self.nt_manager.ensure_note_type(manifest)
        
        for change in sync_resp.changes:
            kind = change.card_kind or "basic"
            nt_def = manifest.supported_note_types.get(kind)
            if not nt_def:
                continue
                
            # Resolve existing card / note_id from SQLite or directly from Anki
            card = self.db.get_card(change.card_id)
            anki_note_id = card.anki_note_id if card else None
            if not anki_note_id:
                anki_note_id = self.note_manager.find_note_by_card_id(change.card_id)
                
            if change.action in ("added", "updated"):
                if not change.fields:
                    continue
                if anki_note_id:
                    self.note_manager.update_note(
                        anki_note_id=anki_note_id,
                        version_id=change.new_card_version_id,
                        fields=change.fields,
                        field_mapping=nt_def["field_mapping"]
                    )
                    stats["updated" if change.action == "updated" else "added"] += 1
                else:
                    anki_note_id = self.note_manager.create_note(
                        deck_id=deck.anki_deck_id,
                        note_type_name=nt_def["note_type"],
                        public_id=change.public_id,
                        card_id=change.card_id,
                        version_id=change.new_card_version_id,
                        tags=change.tags,
                        fields=change.fields,
                        field_mapping=nt_def["field_mapping"]
                    )
                    stats["added" if change.action == "added" else "updated"] += 1
                    
                self.db.upsert_card(RemoteCard(
                    card_id=change.card_id,
                    public_id=change.public_id,
                    card_version_id=change.new_card_version_id,
                    deck_id=deck.deck_id,
                    anki_note_id=anki_note_id,
                    card_kind=kind,
                    content_hash=None,
                    status="active",
                    created_at=now,
                    updated_at=now
                ))
                
            elif change.action == "removed":
                if anki_note_id:
                    self.note_manager.suspend_note(anki_note_id)
                    self.db.upsert_card(RemoteCard(
                        card_id=change.card_id,
                        public_id=change.public_id,
                        card_version_id=change.new_card_version_id,
                        deck_id=deck.deck_id,
                        anki_note_id=anki_note_id,
                        card_kind=kind,
                        content_hash=None,
                        status="removed",
                        created_at=now,
                        updated_at=now
                    ))
                    stats["removed"] += 1
                    
            elif change.action == "deprecated":
                if anki_note_id:
                    self.note_manager.deprecate_note(anki_note_id)
                    self.db.upsert_card(RemoteCard(
                        card_id=change.card_id,
                        public_id=change.public_id,
                        card_version_id=change.new_card_version_id,
                        deck_id=deck.deck_id,
                        anki_note_id=anki_note_id,
                        card_kind=kind,
                        content_hash=None,
                        status="deprecated",
                        created_at=now,
                        updated_at=now
                    ))
                    stats["deprecated"] += 1

        # Update deck release
        deck.latest_release = sync_resp.to_release
        deck.last_sync = now
        deck.updated_at = now
        self.db.upsert_deck(deck)
        
        # Log
        self.db.add_sync_log(SyncLogEntry(
            deck_id=deck.deck_id,
            from_release=sync_resp.from_release,
            to_release=sync_resp.to_release,
            cards_added=stats["added"],
            cards_updated=stats["updated"],
            cards_removed=stats["removed"],
            cards_deprecated=stats["deprecated"],
            synced_at=now,
            duration_ms=None,
            success=True,
            error_message=None
        ))
