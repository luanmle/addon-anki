import logging
from typing import Dict, List, Optional
from aqt import mw

logger = logging.getLogger("anki_concursos.services.note")

class NoteManager:
    def create_note(self, deck_id: int, note_type_name: str, public_id: str, card_id: str, version_id: Optional[str], tags: List[str], fields: Dict[str, str], field_mapping: Dict[str, str]) -> int:
        """Create a new note in Anki. Returns the new Anki Note ID."""
        notetype = mw.col.models.by_name(note_type_name)
        if not notetype:
            raise ValueError(f"Note type {note_type_name} not found")
            
        note = mw.col.new_note(notetype)
        
        # Set metadata
        note["Public ID"] = public_id
        note["Card ID"] = card_id
        note["Version ID"] = version_id or ""
        
        # Set content fields based on mapping
        for f_name, json_key in field_mapping.items():
            if json_key in fields:
                note[f_name] = fields[json_key]
                
        # Set tags
        for t in tags:
            note.add_tag(t)
            
        mw.col.add_note(note, deck_id)
        return note.id

    def update_note(self, anki_note_id: int, version_id: Optional[str], fields: Dict[str, str], field_mapping: Dict[str, str]) -> None:
        """Update an existing note's content without deleting it."""
        try:
            note = mw.col.get_note(anki_note_id)
            
            note["Version ID"] = version_id or ""
            
            for f_name, json_key in field_mapping.items():
                if json_key in fields:
                    note[f_name] = fields[json_key]
                    
            mw.col.update_note(note)
        except Exception as e:
            logger.error(f"Failed to update note {anki_note_id}: {e}")

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
