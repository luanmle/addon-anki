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
from .fields import field_mapping_for_change, note_fields_from_change, protected_fields_for_change

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
            integrity_repairs = self.db.repair_integrity()

            # 1. Get manifest
            manifest = self.api.get_deck_manifest(deck_id)
            
            # 2. Get full sync snapshot
            sync_resp = self.api.sync_deck_all_pages(deck_id, since_release=0)
            
            return {
                "manifest": manifest,
                "sync": sync_resp,
                "integrity_repairs": integrity_repairs,
            }
            
        def on_success(result: dict) -> None:
            manifest = result["manifest"]
            sync_resp = result["sync"]
            integrity_repairs = int(result.get("integrity_repairs", 0))
            
            # Perform mutations on main thread
            mw.progress.start(label="Criando notas no Anki...", immediate=True)
            
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
                duplicate_card_ids = set()
                for change in sync_resp.changes:
                    if change.action == "added" and change.fields:
                        kind = change.card_kind or "basic"
                        note_type_name = (
                            change.note_type
                            if isinstance(getattr(change, "note_type", None), str)
                            else None
                        ) or manifest.supported_note_types.get(kind, {}).get("note_type")
                        if not note_type_name:
                            continue
                            
                        field_mapping = field_mapping_for_change(change, manifest, kind)
                        remote_fields = note_fields_from_change(change.fields, field_mapping)
                        protected_fields = protected_fields_for_change(
                            change, manifest, kind, field_mapping
                        )
                        
                        # Prevent duplication by checking if note already exists in Anki
                        note_ids = self.note_manager.find_note_ids_by_card_id(change.card_id)
                        if len(note_ids) > 1:
                            duplicate_card_ids.add(change.card_id)
                        existing_note_id = note_ids[0] if note_ids else None
                        if existing_note_id:
                            update_kwargs = {
                                "anki_note_id": existing_note_id,
                                "version_id": change.new_card_version_id,
                                "fields": change.fields,
                                "field_mapping": field_mapping,
                            }
                            if protected_fields:
                                update_kwargs["protected_fields"] = protected_fields
                            self.note_manager.update_note(**update_kwargs)
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
                                field_mapping=field_mapping
                            )
                        
                        self.db.upsert_card(RemoteCard(
                            card_id=change.card_id,
                            public_id=change.public_id,
                            card_version_id=change.new_card_version_id,
                            deck_id=deck_id,
                            anki_note_id=note_id,
                            card_kind=kind,
                            content_hash=getattr(change, "content_hash", None),
                            status="active",
                            created_at=now,
                            updated_at=now,
                            remote_fields=remote_fields,
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
                
                mw.progress.finish()
                messages = []
                if integrity_repairs:
                    suffix = "linha" if integrity_repairs == 1 else "linhas"
                    messages.append(f"🧰 Reparadas {integrity_repairs} {suffix} de metadados locais de sync.")
                verb = "Instalado" if count == 1 else "Instalados"
                card_suffix = "card" if count == 1 else "cards"
                messages.append(f"{verb} {count} {card_suffix} com sucesso.")
                if duplicate_card_ids:
                    duplicate_count = len(duplicate_card_ids)
                    suffix = "Card ID" if duplicate_count == 1 else "Card IDs"
                    names = ", ".join(sorted(str(card_id) for card_id in duplicate_card_ids))
                    messages.append(f"⚠️ Encontradas notas locais duplicadas para {duplicate_count} {suffix}: {names}.")
                callback(True, "\n".join(messages))
                
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
        op.with_progress("Buscando dados do baralho no servidor...").run_in_background()
