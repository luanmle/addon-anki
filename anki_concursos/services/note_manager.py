from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set
from aqt import mw

logger = logging.getLogger("anki_concursos.services.note")

class NoteManager:
    def note_exists(self, anki_note_id: int) -> bool:
        """Return whether an Anki note id still exists in the collection."""
        if not mw or not getattr(mw, "col", None):
            return False
        try:
            return mw.col.get_note(anki_note_id) is not None
        except Exception:
            return False

    def note_modified_after(self, anki_note_id: int, timestamp: Optional[str]) -> bool:
        """Return whether an Anki note was modified after a stored sync timestamp."""
        if not timestamp or not mw or not getattr(mw, "col", None):
            return False
        try:
            note = mw.col.get_note(anki_note_id)
            note_mod = getattr(note, "mod", None)
            if note_mod is None:
                return False
            sync_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if sync_time.tzinfo is None:
                sync_time = sync_time.replace(tzinfo=timezone.utc)
            note_time = datetime.fromtimestamp(int(note_mod), tz=timezone.utc)
            return note_time > sync_time.astimezone(timezone.utc)
        except Exception as e:
            logger.error(f"Failed to compare note mod time for note {anki_note_id}: {e}")
            # Fail safe: assume modified so we never silently overwrite a
            # possibly-edited note when the comparison itself errors.
            return True

    def note_differs_from(
        self,
        anki_note_id: int,
        baseline: Optional[Dict[str, str]],
        ignore: Optional[Set[str]] = None,
    ) -> bool:
        """Whether the note's current fields differ from the last-synced baseline.

        `baseline` are the fields the add-on last wrote (keyed by Anki field
        name); `ignore` are field names to skip (e.g. protected fields, kept
        local on purpose). Without a baseline, or on error, assume it differs
        (fail safe — never silently overwrite a possibly-edited note).
        """
        if not baseline or not mw or not getattr(mw, "col", None):
            return True
        skip = ignore or set()
        try:
            note = mw.col.get_note(anki_note_id)
            names = set(note.keys())
            for field_name, value in baseline.items():
                if field_name in skip or field_name not in names:
                    continue
                if note[field_name] != value:
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to compare note fields for note {anki_note_id}: {e}")
            return True

    def find_note_by_card_id(self, card_id: str) -> Optional[int]:
        """Search Anki collection for a note with the given Card ID."""
        note_ids = self.find_note_ids_by_card_id(card_id)
        if len(note_ids) > 1:
            logger.warning("Multiple notes found for Card ID %s: %s", card_id, note_ids)
        return note_ids[0] if note_ids else None

    def find_note_ids_by_card_id(self, card_id: str) -> List[int]:
        """Search Anki collection for notes with the given Card ID."""
        if not mw or not getattr(mw, "col", None):
            return []
        try:
            safe_id = str(card_id).replace('"', '\\"')
            query = f'"Card ID:{safe_id}"'
            note_ids = mw.col.find_notes(query)
            if note_ids and isinstance(note_ids, (list, tuple)):
                return list(note_ids)
        except Exception as e:
            logger.error(f"Failed to find note by Card ID {card_id}: {e}")
        return []

    def create_note(self, deck_id: int, note_type_name: str, public_id: str, card_id: str, version_id: Optional[str], tags: List[str], fields: Dict[str, str], field_mapping: Optional[Dict[str, str]] = None) -> int:
        """Create a new note in Anki. Returns the new Anki Note ID."""
        notetype = mw.col.models.by_name(note_type_name)
        if not notetype:
            raise ValueError(f"Note type {note_type_name} not found")
            
        note = mw.col.new_note(notetype)
        
        # Set metadata
        note["Public ID"] = public_id
        note["Card ID"] = card_id
        note["Version ID"] = version_id or ""
        
        self._apply_fields(note, fields, field_mapping)
                
        # Set tags
        for t in tags:
            note.add_tag(t)
            
        mw.col.add_note(note, deck_id)
        return note.id

    def update_note(
        self,
        anki_note_id: int,
        version_id: Optional[str],
        fields: Dict[str, str],
        field_mapping: Optional[Dict[str, str]] = None,
        protected_fields: Optional[Set[str]] = None,
    ) -> bool:
        """Update an existing note's content without deleting it.

        Returns True on success, False on failure. Callers must check the
        return value before recording the new content_hash — storing a new
        hash after a failed write causes permanent desync (card skipped
        forever on subsequent syncs).
        """
        try:
            note = mw.col.get_note(anki_note_id)

            note["Version ID"] = version_id or ""

            self._apply_fields(note, fields, field_mapping, protected_fields=protected_fields)

            mw.col.update_note(note)
            return True
        except Exception as e:
            logger.error(f"Failed to update note {anki_note_id}: {e}")
            return False

    def _apply_fields(
        self,
        note: Any,
        fields: Dict[str, str],
        field_mapping: Optional[Dict[str, str]],
        protected_fields: Optional[Set[str]] = None,
    ) -> None:
        consumed: set = set()
        protected = protected_fields or set()
        if field_mapping:
            for f_name, json_key in field_mapping.items():
                if f_name in protected:
                    continue
                if json_key in fields:
                    note[f_name] = fields[json_key]
                    consumed.add(json_key)
                elif f_name in fields:
                    note[f_name] = fields[f_name]
                    consumed.add(f_name)

            # A mapping that omits a field must not silently drop its content:
            # apply remaining keys that match a real note field.
            try:
                valid_names = set(note.keys())
            except Exception:
                valid_names = set()
            for field_name, value in fields.items():
                if (
                    field_name in consumed
                    or field_name in protected
                    or field_name not in valid_names
                ):
                    continue
                try:
                    note[field_name] = value
                except Exception:
                    continue
            return

        for field_name, value in fields.items():
            if field_name in protected:
                continue
            try:
                note[field_name] = value
            except Exception:
                continue

    def suspend_note(self, anki_note_id: int) -> None:
        """Suspend all cards of a note."""
        try:
            card_ids = mw.col.card_ids_of_note(anki_note_id)
            if card_ids:
                mw.col.sched.suspend_cards(card_ids)
        except Exception as e:
            logger.error(f"Failed to suspend cards for note {anki_note_id}: {e}")

    def deprecate_note(self, anki_note_id: int) -> None:
        """Suspend cards and tag as deprecated."""
        try:
            note = mw.col.get_note(anki_note_id)
            note.add_tag("AnkiConcursos::deprecated")
            mw.col.update_note(note)
            
            card_ids = mw.col.card_ids_of_note(anki_note_id)
            if card_ids:
                mw.col.sched.suspend_cards(card_ids)
        except Exception as e:
            logger.error(f"Failed to deprecate note {anki_note_id}: {e}")
