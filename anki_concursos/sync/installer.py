import logging
from datetime import datetime, timezone
from typing import Callable

from aqt import mw
from aqt.operations import QueryOp

from ..api.client import ApiClient
from ..storage.database import DatabaseManager
from ..storage.models import RemoteDeck, RemoteCard, SyncLogEntry
from ..services.note_type_manager import NoteTypeManager
from ..services.deck_manager import DeckManager
from ..services.note_manager import NoteManager

logger = logging.getLogger("anki_concursos.sync.installer")

class DeckInstaller:
    def __init__(self, api: ApiClient, db: DatabaseManager):
        self.api = api
        self.db = db
        self.nt_manager = NoteTypeManager()
        self.deck_manager = DeckManager()
        self.note_manager = NoteManager()

    def install_deck(self, deck_id: str, callback: Callable[[bool, str], None]) -> None:
        """Installs a deck. Runs in a background thread using QueryOp."""
        
        def background_job() -> dict:
            # 1. Get manifest
            manifest = self.api.get_deck_manifest(deck_id)
            
            # 2. Get full sync snapshot
            sync_resp = self.api.sync_deck_all_pages(deck_id, since_release=0)
            
            return {"manifest": manifest, "sync": sync_resp}
            
        def on_success(result: dict) -> None:
            manifest = result["manifest"]
            sync_resp = result["sync"]
            
            # Perform mutations on main thread
            mw.progress.start(label="Creating Anki notes...", immediate=True)
            
            try:
                # 1. Note types & Deck
                self.nt_manager.ensure_note_type(manifest)
                anki_deck_id = self.deck_manager.ensure_deck(manifest.name)
                
                # Save to DB
                now = datetime.now(timezone.utc).isoformat()
                remote_deck = RemoteDeck(
                    deck_id=deck_id,
                    deck_name=manifest.name,
                    anki_deck_id=anki_deck_id,
                    note_type_name=manifest.note_type,
                    latest_release=sync_resp.to_release,
                    last_sync=now,
                    created_at=now,
                    updated_at=now
                )
                self.db.upsert_deck(remote_deck)
                
                # 2. Add notes
                count = 0
                for change in sync_resp.changes:
                    if change.action == "added" and change.fields:
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
                        
                        # Prevent duplication by checking if note already exists in Anki
                        existing_note_id = self.note_manager.find_note_by_card_id(change.card_id)
                        if existing_note_id:
                            self.note_manager.update_note(
                                anki_note_id=existing_note_id,
                                version_id=change.new_card_version_id,
                                fields=change.fields,
                                field_mapping=None if use_native_fields else manifest.supported_note_types.get(kind, {}).get("field_mapping")
                            )
                            note_id = existing_note_id
                        else:
                            note_id = self.note_manager.create_note(
                                deck_id=anki_deck_id,
                                note_type_name=note_type_name,
                                public_id=change.public_id,
                                card_id=change.card_id,
                                version_id=change.new_card_version_id,
                                tags=change.tags,
                                fields=change.fields,
                                field_mapping=None if use_native_fields else manifest.supported_note_types.get(kind, {}).get("field_mapping")
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
                            updated_at=now
                        ))
                        count += 1
                        
                # Log success
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
                    error_message=None
                ))
                
                self._refresh_anki_ui()
                mw.progress.finish()
                callback(True, f"Successfully installed {count} cards.")
                
            except Exception as e:
                mw.progress.finish()
                logger.exception("Failed to install deck notes")
                callback(False, str(e))

        # Start the background op
        op = QueryOp(
            parent=mw,
            op=lambda _: background_job(),
            success=on_success
        )
        op.failure(lambda exc: callback(False, str(exc)))
        op.with_progress("Fetching deck data from server...").run_in_background()

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

