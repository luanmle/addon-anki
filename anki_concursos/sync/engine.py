import logging
import re
from datetime import datetime, timezone
from typing import Callable, List, Dict, Optional

from aqt import mw
from aqt.operations import QueryOp

from ..api.client import ApiClient
from ..storage.database import DatabaseManager
from ..storage.models import RemoteDeck, RemoteCard, SyncLogEntry
from ..services.note_type_manager import NoteTypeManager
from ..services.note_manager import NoteManager
from .backup import BackupManager
from .fields import field_mapping_for_change, note_fields_from_change, protected_fields_for_change

logger = logging.getLogger("anki_concursos.sync.engine")

class SyncEngine:
    def __init__(self, api: ApiClient, db: DatabaseManager):
        self.api = api
        self.db = db
        self.nt_manager = NoteTypeManager()
        self.note_manager = NoteManager()
        self.backup_manager = BackupManager(db.db_path)
        self._duplicate_card_ids = set()

    def sync_all(self, callback: Callable[[bool, str], None]) -> None:
        """Sync all installed decks incrementally."""
        decks = self.db.get_all_decks()
        if not decks:
            self._bootstrap_subscribed_decks(callback)
            return
            
        def background_job() -> dict:
            integrity_repairs = self.db.repair_integrity()

            # 1. Check version compatibility first (global; aborts all decks).
            self._assert_version_supported(self.api.get_addon_status())

            # 2. Reconcile platform subscriptions before local deck sync.
            subscriptions = self.api.list_subscriptions()
            subscribed_ids = {
                sub.deck_id
                for sub in subscriptions.items
                if sub.unsubscribed_at is None
            }
            active_decks = []
            stale_decks = []
            for deck in decks:
                if deck.deck_id in subscribed_ids:
                    active_decks.append(deck)
                else:
                    self.db.delete_deck(deck.deck_id)
                    stale_decks.append(deck.deck_name)

            # 3. Fetch updates per deck in isolation: one failing deck
            # (unsubscribed/deleted/network) must not abort the others.
            results = []
            install_results = []
            errors = []
            for deck in active_decks:
                try:
                    manifest = self.api.get_deck_manifest(deck.deck_id)
                    sync_resp = self.api.sync_deck_all_pages(
                        deck.deck_id, since_release=deck.latest_release
                    )
                    state = self.api.get_deck_state(deck.deck_id)
                    results.append({
                        "deck": deck,
                        "manifest": manifest,
                        "sync": sync_resp,
                        "state": state,
                    })
                except Exception as e:
                    logger.exception("Failed to fetch updates for deck %s", deck.deck_id)
                    errors.append(f"{deck.deck_name}: {e}")

            installed_ids = {deck.deck_id for deck in active_decks}
            for deck_id in subscribed_ids:
                if deck_id in installed_ids or self.db.get_deck(deck_id):
                    continue
                try:
                    install_results.append(
                        {
                            "deck_id": deck_id,
                            "manifest": self.api.get_deck_manifest(deck_id),
                            "sync": self.api.sync_deck_all_pages(deck_id, since_release=0),
                        }
                    )
                except Exception as e:
                    logger.exception("Failed to fetch new subscribed deck %s", deck_id)
                    errors.append(f"{deck_id}: {e}")

            return {
                "results": results,
                "install_results": install_results,
                "errors": errors,
                "stale_decks": stale_decks,
                "integrity_repairs": integrity_repairs,
            }

        def on_success(payload: dict) -> None:
            # We are back on the main thread
            results = payload["results"]
            install_results = payload["install_results"]
            errors = list(payload["errors"])
            stale_decks = list(payload.get("stale_decks", []))
            integrity_repairs = int(payload.get("integrity_repairs", 0))

            # Count total changes; also reconcile upstream deletions even when
            # there are no content changes (orphan-only case).
            total_changes = sum(len(r["sync"].changes) for r in results)
            needs_reconcile = self._any_orphans(results)
            if total_changes == 0 and not needs_reconcile and not install_results:
                stale_msg = self._stale_deck_message(stale_decks)
                repair_msg = self._integrity_repair_message(integrity_repairs)
                if errors:
                    prefix = "\n".join(msg for msg in (repair_msg, stale_msg) if msg)
                    if prefix:
                        callback(
                            True,
                            prefix
                            + "\n⚠️ Alguns baralhos não puderam ser buscados:\n"
                            + "\n".join(errors),
                        )
                    else:
                        callback(
                            False,
                            "⚠️ Falha ao sincronizar alguns baralhos:\n" + "\n".join(errors),
                        )
                elif repair_msg or stale_msg:
                    callback(True, "\n".join(msg for msg in (repair_msg, stale_msg) if msg))
                else:
                    callback(True, "Tudo atualizado.")
                return

            local_conflicts = []
            for res in results:
                local_conflicts.extend(
                    self._find_local_update_conflicts(
                        res["deck"], res["manifest"], res["sync"]
                    )
                )
            if local_conflicts:
                callback(False, self._local_conflict_message(local_conflicts))
                return

            mw.progress.start(label="Aplicando atualizações...", immediate=True)

            # Create backup before applying
            backup_path = self.backup_manager.create_backup()

            # Group every collection mutation into one undo entry so a single
            # Ctrl+Z reverts the whole sync if it fails partway.
            undo_handle = self._begin_undo("Anki Concursos: Sincronização")

            applied_ops = 0
            installed = 0
            installed_changes = 0
            self._duplicate_card_ids = set()
            try:
                for item in install_results:
                    installed_changes += self._install_bootstrap_deck(
                        deck_id=item["deck_id"],
                        manifest=item["manifest"],
                        sync_resp=item["sync"],
                    )
                    installed += 1

                for res in results:
                    applied_ops += self._apply_deck_sync(
                        res["deck"], res["manifest"], res["sync"], res.get("state")
                    )

                self._merge_undo(undo_handle)
                mw.progress.finish()
            except Exception as e:
                mw.progress.finish()
                logger.exception("Sync failed during application")
                # Roll back the add-on DB; group the partial collection changes
                # so one Undo reverts them. Re-running sync is also idempotent
                # (notes are matched by Card ID).
                self.backup_manager.restore_backup(backup_path)
                self._merge_undo(undo_handle)
                callback(False, f"Falha na sincronização: {str(e)}. O banco local foi restaurado. Use Desfazer do Anki (Ctrl+Z) para reverter alterações nos cards.")
                return

            messages = []
            if integrity_repairs:
                messages.append(self._integrity_repair_message(integrity_repairs))
            total_changes += installed_changes
            if installed:
                messages.append(
                    self._install_message(
                        installed,
                        [item["manifest"].name for item in install_results],
                    )
                )
            if total_changes > 0:
                messages.append(f"🔄 Sincronizadas {total_changes} {self._plural(total_changes, 'alteração', 'alterações')}.")
            elif applied_ops > 0:
                verb = "Reconciliado" if applied_ops == 1 else "Reconciliados"
                messages.append(f"🧹 {verb} {applied_ops} {self._plural(applied_ops, 'card removido', 'cards removidos')}.")
            if stale_decks:
                messages.append(self._stale_deck_message(stale_decks))
            duplicate_msg = self._duplicate_card_ids_message(self._duplicate_card_ids)
            if duplicate_msg:
                messages.append(duplicate_msg)
            msg = "\n".join(messages) or "Tudo atualizado."

            if errors:
                callback(
                    True,
                    msg + "\n⚠️ Alguns baralhos não puderam ser buscados:\n" + "\n".join(errors),
                )
            else:
                callback(True, msg)

        op = QueryOp(
            parent=mw,
            op=lambda _: background_job(),
            success=on_success
        )
        op.failure(lambda exc: callback(False, str(exc)))
        op.with_progress("Verificando atualizações...").run_in_background()

    @staticmethod
    def _install_message(count: int, deck_names: List[str]) -> str:
        if count <= 0:
            return ""
        verb = "Instalado" if count == 1 else "Instalados"
        suffix = "baralho inscrito" if count == 1 else "baralhos inscritos"
        names = ", ".join(name for name in deck_names if name)
        if names:
            return f"📥 {verb} {count} {suffix}: {names}."
        return f"📥 {verb} {count} {suffix}."

    @staticmethod
    def _stale_deck_message(deck_names: List[str]) -> str:
        count = len(deck_names)
        if count <= 0:
            return ""
        suffix = "baralho sem inscrição" if count == 1 else "baralhos sem inscrição"
        names = ", ".join(name for name in deck_names if name)
        if names:
            return f"🗑️ Removido rastreamento local de {count} {suffix}: {names}."
        return f"🗑️ Removido rastreamento local de {count} {suffix}."

    @staticmethod
    def _integrity_repair_message(count: int) -> str:
        if count <= 0:
            return ""
        suffix = "linha" if count == 1 else "linhas"
        return f"🧰 Reparadas {count} {suffix} de metadados locais de sync."

    @staticmethod
    def _duplicate_card_ids_message(card_ids: set) -> str:
        if not card_ids:
            return ""
        count = len(card_ids)
        suffix = "Card ID" if count == 1 else "Card IDs"
        names = ", ".join(sorted(str(card_id) for card_id in card_ids))
        return f"⚠️ Encontradas notas locais duplicadas para {count} {suffix}: {names}."

    def _find_local_update_conflicts(self, deck: RemoteDeck, manifest, sync_resp) -> List[str]:
        conflicts = []
        for change in (getattr(sync_resp, "changes", None) or []):
            if getattr(change, "action", None) != "updated":
                continue
            card = self.db.get_card(change.card_id)
            if not card or not card.anki_note_id:
                continue
            new_hash = getattr(change, "content_hash", None)
            if new_hash and card.content_hash == new_hash:
                continue
            anki_note_id = self._resolve_anki_note_id(card, change.card_id)
            if not anki_note_id:
                continue
            if not self.note_manager.note_modified_after(anki_note_id, card.updated_at):
                continue
            # A newer mod time alone is noisy (tags, note-type tweaks, reposition
            # all bump it). Only conflict if the tracked content actually differs
            # from the last-synced baseline, ignoring protected fields.
            kind = change.card_kind or "basic"
            field_mapping = field_mapping_for_change(change, manifest, kind)
            protected = protected_fields_for_change(change, manifest, kind, field_mapping)
            if self.note_manager.note_differs_from(
                anki_note_id, card.remote_fields, ignore=protected
            ):
                conflicts.append(f"{deck.deck_name}: {change.public_id}")
        return conflicts

    @staticmethod
    def _local_conflict_message(conflicts: List[str]) -> str:
        count = len(conflicts)
        suffix = "card" if count == 1 else "cards"
        names = ", ".join(conflicts[:10])
        extra = "" if count <= 10 else f" e mais {count - 10}"
        return (
            f"⚠️ Conflito local detectado em {count} {suffix}: {names}{extra}.\n"
            "A sincronização foi interrompida antes de sobrescrever alterações locais. "
            "Revise esses cards no Anki e tente sincronizar novamente."
        )

    @staticmethod
    def _plural(count: int, singular: str, plural: str) -> str:
        return singular if count == 1 else plural

    def _bootstrap_subscribed_decks(self, callback: Callable[[bool, str], None]) -> None:
        def background_job() -> dict:
            integrity_repairs = self.db.repair_integrity()
            self._assert_version_supported(self.api.get_addon_status())

            subscriptions = self.api.list_subscriptions()
            subscribed_ids = [
                sub.deck_id
                for sub in subscriptions.items
                if sub.unsubscribed_at is None
            ]

            results = []
            errors = []
            for deck_id in subscribed_ids:
                if self.db.get_deck(deck_id):
                    continue
                try:
                    results.append(
                        {
                            "deck_id": deck_id,
                            "manifest": self.api.get_deck_manifest(deck_id),
                            "sync": self.api.sync_deck_all_pages(deck_id, since_release=0),
                        }
                    )
                except Exception as e:
                    logger.exception("Failed to bootstrap deck %s", deck_id)
                    errors.append(f"{deck_id}: {e}")
            return {
                "results": results,
                "errors": errors,
                "integrity_repairs": integrity_repairs,
            }

        def on_success(payload: dict) -> None:
            results = payload["results"]
            errors = list(payload["errors"])
            integrity_repairs = int(payload.get("integrity_repairs", 0))
            repair_msg = self._integrity_repair_message(integrity_repairs)
            if not results:
                if errors:
                    prefix = repair_msg + "\n" if repair_msg else ""
                    callback(False, prefix + "Falha ao instalar baralhos:\n" + "\n".join(errors))
                elif repair_msg:
                    callback(True, repair_msg)
                else:
                    callback(True, "Nenhum baralho instalado para sincronizar.")
                return

            mw.progress.start(
                label=f"Instalando {len(results)} baralhos inscritos...",
                immediate=True,
            )
            undo_handle = self._begin_undo("Anki Concursos: Instalação")
            installed = 0
            try:
                for item in results:
                    try:
                        self._install_bootstrap_deck(
                            deck_id=item["deck_id"],
                            manifest=item["manifest"],
                            sync_resp=item["sync"],
                        )
                        installed += 1
                    except Exception as e:
                        logger.exception("Bootstrap failed for deck %s", item["deck_id"])
                        errors.append(f"{item['deck_id']}: {e}")

                self._merge_undo(undo_handle)
                mw.progress.finish()
            except Exception as e:
                mw.progress.finish()
                logger.exception("Bootstrap sync failed")
                self._merge_undo(undo_handle)
                callback(False, f"Falha na sincronização: {str(e)}")
                return

            if errors:
                prefix = repair_msg + "\n" if repair_msg else ""
                callback(
                    installed > 0,
                    prefix + self._bootstrap_install_message(installed) + " Falhas:\n" + "\n".join(errors),
                )
            else:
                messages = [
                    msg for msg in (
                        repair_msg,
                        self._bootstrap_install_message(installed) + " Execute a sincronização novamente para buscar atualizações.",
                    )
                    if msg
                ]
                callback(True, "\n".join(messages))

        op = QueryOp(
            parent=mw,
            op=lambda _: background_job(),
            success=on_success,
        )
        op.failure(lambda exc: callback(False, str(exc)))
        op.with_progress("Verificando inscrições...").run_in_background()

    @staticmethod
    def _bootstrap_install_message(count: int) -> str:
        verb = "Instalado" if count == 1 else "Instalados"
        suffix = "baralho inscrito" if count == 1 else "baralhos inscritos"
        return f"{verb} {count} {suffix}."

    def _assert_version_supported(self, status: dict) -> None:
        """Raise if the installed add-on is older than the server minimum.

        Parsing is defensive: a non-numeric version segment must never crash
        sync — it is treated as 0, not re-raised as a fatal error.
        """
        min_ver = status.get("min_addon_version") if isinstance(status, dict) else None
        if not min_ver:
            return
        from ..consts import VERSION
        if self._version_is_outdated(VERSION, min_ver):
            raise ValueError(
                f"Sua versão do add-on ({VERSION}) é obsoleta. "
                f"A versão mínima suportada é {min_ver}. Por favor, atualize o add-on."
            )

    @staticmethod
    def _version_is_outdated(current: str, minimum: str) -> bool:
        def parse(value: str) -> List[int]:
            parts: List[int] = []
            for segment in str(value).split("."):
                match = re.match(r"\d+", segment.strip())
                parts.append(int(match.group()) if match else 0)
            return parts

        current_parts = parse(current)
        minimum_parts = parse(minimum)
        length = max(len(current_parts), len(minimum_parts))
        current_parts += [0] * (length - len(current_parts))
        minimum_parts += [0] * (length - len(minimum_parts))
        return current_parts < minimum_parts

    @staticmethod
    def _begin_undo(name: str):
        """Open a custom undo entry so the sync is a single undoable action.

        Best-effort: returns a handle or None if the Anki API is unavailable.
        """
        try:
            return mw.col.add_custom_undo_entry(name)
        except Exception:
            return None

    @staticmethod
    def _merge_undo(handle) -> None:
        if handle is None:
            return
        try:
            mw.col.merge_undo_entries(handle)
        except Exception:
            pass

    def _install_bootstrap_deck(self, deck_id: str, manifest, sync_resp) -> int:
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
        count = 0
        for change in sync_resp.changes:
            if change.action != "added" or not change.fields:
                continue
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
            existing_note_id = self.note_manager.find_note_by_card_id(change.card_id)
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
                    field_mapping=field_mapping,
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
        return count

    def _ensure_deck(self, deck_name: str) -> int:
        from ..services.deck_manager import DeckManager
        return DeckManager().ensure_deck(deck_name)

    def _apply_deck_sync(self, deck: RemoteDeck, manifest, sync_resp, state=None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        stats = {"added": 0, "updated": 0, "removed": 0, "deprecated": 0}

        has_changes = bool(getattr(sync_resp, "has_changes", False) and sync_resp.changes)

        if has_changes:
            # Ensure note types
            self.nt_manager.ensure_note_type(manifest)

        for change in (sync_resp.changes if has_changes else []):
            kind = change.card_kind or "basic"
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
                
            card = self.db.get_card(change.card_id)
            anki_note_id = self._resolve_anki_note_id(card, change.card_id)
                
            if change.action in ("added", "updated"):
                if not change.fields:
                    continue
                field_mapping = field_mapping_for_change(change, manifest, kind)
                remote_fields = note_fields_from_change(change.fields, field_mapping)
                protected_fields = protected_fields_for_change(
                    change, manifest, kind, field_mapping
                )
                new_hash = getattr(change, "content_hash", None)
                if anki_note_id:
                    # Skip the collection write when content is unchanged: it
                    # would only bump the note's mod time and cause needless
                    # AnkiWeb sync churn.
                    if not (new_hash and card and card.content_hash == new_hash):
                        update_kwargs = {
                            "anki_note_id": anki_note_id,
                            "version_id": change.new_card_version_id,
                            "fields": change.fields,
                            "field_mapping": field_mapping,
                        }
                        if protected_fields:
                            update_kwargs["protected_fields"] = protected_fields
                        self.note_manager.update_note(**update_kwargs)
                else:
                    deck.anki_deck_id = self._resolve_anki_deck_id(deck)
                    anki_note_id = self.note_manager.create_note(
                        deck_id=deck.anki_deck_id,
                        note_type_name=note_type_name,
                        public_id=change.public_id,
                        card_id=change.card_id,
                        version_id=change.new_card_version_id,
                        tags=change.tags,
                        fields=change.fields,
                        field_mapping=field_mapping
                    )
                # Count by the action the server reported, not by local state.
                stats["updated" if change.action == "updated" else "added"] += 1

                self.db.upsert_card(RemoteCard(
                    card_id=change.card_id,
                    public_id=change.public_id,
                    card_version_id=change.new_card_version_id,
                    deck_id=deck.deck_id,
                    anki_note_id=anki_note_id,
                    card_kind=kind,
                    content_hash=new_hash,
                    status="active",
                    created_at=now,
                    updated_at=now,
                    remote_fields=remote_fields,
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

        # Reconcile orphans: suspend local active cards that no longer exist
        # upstream (hard-deleted / history squashed) and were therefore never
        # delivered as a `removed` change. Only when the full-state snapshot
        # lines up with the release we just synced.
        if state is not None and getattr(sync_resp, "to_release", None) == getattr(
            state, "latest_release", None
        ):
            upstream_ids = {
                getattr(c, "card_id", None) for c in (getattr(state, "cards", None) or [])
            }
            for local in self.db.get_active_cards_by_deck(deck.deck_id):
                if local.card_id in upstream_ids:
                    continue
                anki_note_id = self._resolve_anki_note_id(local, local.card_id)
                if anki_note_id:
                    self.note_manager.suspend_note(anki_note_id)
                self.db.upsert_card(RemoteCard(
                    card_id=local.card_id,
                    public_id=local.public_id,
                    card_version_id=local.card_version_id,
                    deck_id=deck.deck_id,
                    anki_note_id=anki_note_id,
                    card_kind=local.card_kind,
                    content_hash=local.content_hash,
                    status="removed",
                    created_at=local.created_at or now,
                    updated_at=now,
                ))
                stats["removed"] += 1

        # Nothing applied and nothing reconciled: leave watermark/log untouched.
        if not has_changes and not any(stats.values()):
            return 0

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
        return sum(stats.values())

    def _resolve_anki_note_id(self, card: Optional[RemoteCard], card_id: str) -> Optional[int]:
        local_note_id = card.anki_note_id if card else None
        note_ids = self.note_manager.find_note_ids_by_card_id(card_id)
        if len(note_ids) > 1:
            self._duplicate_card_ids.add(card_id)
        if local_note_id and self.note_manager.note_exists(local_note_id):
            return local_note_id
        return note_ids[0] if note_ids else None

    def _resolve_anki_deck_id(self, deck: RemoteDeck) -> int:
        if deck.anki_deck_id and self._deck_exists(deck.anki_deck_id):
            return deck.anki_deck_id
        return self._ensure_deck(deck.deck_name)

    def _deck_exists(self, anki_deck_id: int) -> bool:
        from ..services.deck_manager import DeckManager
        return DeckManager().deck_exists(anki_deck_id)

    def _any_orphans(self, results) -> bool:
        """Cheap pre-check: does any deck have local active cards missing from
        the upstream full-state snapshot? Keeps idle syncs backup-free."""
        for res in results:
            state = res.get("state")
            sync_resp = res["sync"]
            if state is None or getattr(sync_resp, "to_release", None) != getattr(
                state, "latest_release", None
            ):
                continue
            upstream_ids = {
                getattr(c, "card_id", None) for c in (getattr(state, "cards", None) or [])
            }
            local = self.db.get_active_cards_by_deck(res["deck"].deck_id)
            if any(lc.card_id not in upstream_ids for lc in local):
                return True
        return False
