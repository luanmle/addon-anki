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
            self._bootstrap_subscribed_decks(callback)
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

            # Fetch updates for all decks (content + template deltas)
            results = []
            for deck in decks:
                manifest = self.api.get_deck_manifest(deck.deck_id)
                sync_resp = self.api.sync_deck_all_pages(deck.deck_id, since_release=deck.latest_release)
                template_sync = self.api.sync_deck_templates(deck.deck_id, since_version=deck.latest_template_version)
                results.append({
                    "deck": deck,
                    "manifest": manifest,
                    "sync": sync_resp,
                    "template_sync": template_sync,
                })
            return results

        def on_success(results: List[dict]) -> None:
            # We are back on the main thread
            now = datetime.now(timezone.utc).isoformat()

            total_content = sum(len(r["sync"].changes) for r in results)
            total_templates = sum(len(r["template_sync"].changes) for r in results)

            if total_content == 0 and total_templates == 0:
                callback(True, "Already up to date.")
                return

            label = f"Applying {total_content} updates" + (
                f", {total_templates} template changes" if total_templates else ""
            ) + "..."
            mw.progress.start(label=label, immediate=True)

            # Create backup before applying
            backup_path = self.backup_manager.create_backup()

            try:
                for res in results:
                    deck = res["deck"]
                    template_sync = res["template_sync"]

                    # Apply template structure changes first so note content uses
                    # the correct field layout.
                    if template_sync.has_changes:
                        self.nt_manager.apply_template_versions(template_sync.changes)
                        deck.latest_template_version = template_sync.to_version
                        deck.updated_at = now
                        self.db.upsert_deck(deck)

                    self._apply_deck_sync(deck, res["manifest"], res["sync"])

                mw.progress.finish()
                if total_templates and total_content:
                    callback(True, f"Successfully synced {total_content} changes, {total_templates} template update(s).")
                elif total_templates:
                    callback(True, f"Templates atualizados: {total_templates}.")
                else:
                    callback(True, f"Successfully synced {total_content} changes.")

            except Exception as e:
                mw.progress.finish()
                logger.exception("Sync failed during application")
                self.backup_manager.restore_backup(backup_path)
                callback(False, f"Sync failed: {str(e)}. Local database was rolled back. You may need to use Anki's Undo if cards were modified.")
                
        op = QueryOp(
            parent=mw,
            op=lambda _: background_job(),
            success=on_success
        )
        op.failure(lambda exc: callback(False, str(exc)))
        op.with_progress("Checking for updates...").run_in_background()

    def _bootstrap_subscribed_decks(self, callback: Callable[[bool, str], None]) -> None:
        def background_job() -> list[dict]:
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
                    pass

            subscriptions = self.api.list_subscriptions()
            subscribed_ids = [
                sub.deck_id
                for sub in subscriptions.items
                if sub.unsubscribed_at is None
            ]
            if not subscribed_ids:
                return []
            return [
                {
                    "deck_id": deck_id,
                    "manifest": self.api.get_deck_manifest(deck_id),
                    "sync": self.api.sync_deck_all_pages(deck_id, since_release=0),
                }
                for deck_id in subscribed_ids
                if not self.db.get_deck(deck_id)
            ]

        def on_success(results: list[dict]) -> None:
            if not results:
                callback(True, "No installed decks to sync.")
                return

            mw.progress.start(
                label=f"Installing {len(results)} subscribed decks...",
                immediate=True,
            )
            try:
                installed = 0
                for item in results:
                    self._install_bootstrap_deck(
                        deck_id=item["deck_id"],
                        manifest=item["manifest"],
                        sync_resp=item["sync"],
                    )
                    installed += 1

                self._refresh_anki_ui()
                mw.progress.finish()
                callback(True, f"Installed {installed} subscribed decks. Run sync again to fetch updates.")
            except Exception as e:
                mw.progress.finish()
                logger.exception("Bootstrap sync failed")
                callback(False, f"Sync failed: {str(e)}")

        op = QueryOp(
            parent=mw,
            op=lambda _: background_job(),
            success=on_success,
        )
        op.failure(lambda exc: callback(False, str(exc)))
        op.with_progress("Checking subscriptions...").run_in_background()

    def _install_bootstrap_deck(self, deck_id: str, manifest, sync_resp) -> None:
        self.nt_manager.ensure_note_type(manifest)
        anki_deck_id = self._ensure_deck(manifest.name)
        now = datetime.now(timezone.utc).isoformat()
        remote_deck = RemoteDeck(
            deck_id=deck_id,
            deck_name=manifest.name,
            anki_deck_id=anki_deck_id,
            note_type_name=manifest.note_type,
            latest_release=sync_resp.to_release,
            last_sync=now,
            created_at=now,
            updated_at=now,
        )
        self.db.upsert_deck(remote_deck)
        deck_id_cache: dict = {manifest.name: anki_deck_id}
        count = 0
        for change in sync_resp.changes:
            if change.action != "added" or not change.fields:
                continue
            kind = change.card_kind or "basic"
            template = change.template if isinstance(change.template, dict) else None
            note_type_name = (
                change.note_type
                if isinstance(getattr(change, "note_type", None), str)
                else None
            ) or manifest.supported_note_types.get(kind, {}).get("note_type")
            if not note_type_name:
                continue
            use_native_fields = bool(template and change.fields)
            existing_note_id = self.note_manager.find_note_by_card_id(change.card_id)
            if existing_note_id:
                self.note_manager.update_note(
                    anki_note_id=existing_note_id,
                    version_id=change.new_card_version_id,
                    fields=change.fields,
                    field_mapping=None if use_native_fields else manifest.supported_note_types.get(kind, {}).get("field_mapping"),
                )
                note_id = existing_note_id
            else:
                note_deck_path = getattr(change, "source_deck_path", None) or manifest.name
                if note_deck_path not in deck_id_cache:
                    deck_id_cache[note_deck_path] = self._ensure_deck(note_deck_path)
                note_id = self.note_manager.create_note(
                    deck_id=deck_id_cache[note_deck_path],
                    note_type_name=note_type_name,
                    public_id=change.public_id,
                    card_id=change.card_id,
                    version_id=change.new_card_version_id,
                    tags=change.tags,
                    fields=change.fields,
                    field_mapping=None if use_native_fields else manifest.supported_note_types.get(kind, {}).get("field_mapping"),
                )
            self.db.upsert_card(RemoteCard(
                card_id=change.card_id,
                public_id=change.public_id,
                card_version_id=change.new_card_version_id,
                deck_id=deck_id,
                anki_note_id=note_id,
                card_kind=kind,
                content_hash=None,
                status="active",
                created_at=now,
                updated_at=now,
            ))
            count += 1
        self.db.add_sync_log(SyncLogEntry(
            deck_id=deck_id,
            from_release=0,
            to_release=sync_resp.to_release,
            cards_added=count,
            cards_updated=0,
            cards_removed=0,
            cards_deprecated=0,
            synced_at=now,
            duration_ms=None,
            success=True,
            error_message=None,
        ))

    def _ensure_deck(self, deck_name: str) -> int:
        from ..services.deck_manager import DeckManager
        return DeckManager().ensure_deck(deck_name)

    @staticmethod
    def _refresh_anki_ui() -> None:
        try:
            if mw and getattr(mw, "deckBrowser", None):
                mw.deckBrowser.refresh()
        except Exception:
            pass
        try:
            if mw:
                mw.reset()
        except Exception:
            pass

    def _apply_deck_sync(self, deck: RemoteDeck, manifest, sync_resp) -> None:
        if not sync_resp.has_changes or not sync_resp.changes:
            return
            
        now = datetime.now(timezone.utc).isoformat()
        stats = {"added": 0, "updated": 0, "removed": 0, "deprecated": 0}
        deck_id_cache: dict = {deck.deck_name: deck.anki_deck_id}

        # Ensure note types
        self.nt_manager.ensure_note_type(manifest)

        for change in sync_resp.changes:
            kind = change.card_kind or "basic"
            template = change.template if isinstance(change.template, dict) else None
            note_type_name = (
                change.note_type
                if isinstance(getattr(change, "note_type", None), str)
                else None
            ) or manifest.supported_note_types.get(kind, {}).get("note_type")
            template_name = (
                change.template_name
                if isinstance(getattr(change, "template_name", None), str)
                else None
            )
            if not note_type_name:
                continue
                
            # Resolve existing card / note_id from SQLite or directly from Anki
            card = self.db.get_card(change.card_id)
            anki_note_id = card.anki_note_id if card else None
            if not anki_note_id:
                anki_note_id = self.note_manager.find_note_by_card_id(change.card_id)
                
            if change.action in ("added", "updated"):
                if not change.fields:
                    continue
                use_native_fields = bool(template and change.fields)
                if anki_note_id:
                    self.note_manager.update_note(
                        anki_note_id=anki_note_id,
                        version_id=change.new_card_version_id,
                        fields=change.fields,
                        field_mapping=None if use_native_fields else manifest.supported_note_types.get(kind, {}).get("field_mapping")
                    )
                    stats["updated" if change.action == "updated" else "added"] += 1
                else:
                    note_deck_path = getattr(change, "source_deck_path", None) or deck.deck_name
                    if note_deck_path not in deck_id_cache:
                        deck_id_cache[note_deck_path] = self._ensure_deck(note_deck_path)
                    anki_note_id = self.note_manager.create_note(
                        deck_id=deck_id_cache[note_deck_path],
                        note_type_name=note_type_name,
                        public_id=change.public_id,
                        card_id=change.card_id,
                        version_id=change.new_card_version_id,
                        tags=change.tags,
                        fields=change.fields,
                        field_mapping=None if use_native_fields else manifest.supported_note_types.get(kind, {}).get("field_mapping")
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
