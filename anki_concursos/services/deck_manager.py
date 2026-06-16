import logging
from aqt import mw

logger = logging.getLogger("anki_concursos.services.deck")

class DeckManager:
    def ensure_deck(self, name: str) -> int:
        """Create deck 'Anki Concursos::{name}' if it doesn't exist. Returns deck ID."""
        full_name = f"Anki Concursos::{name}"
        deck_id = mw.col.decks.id(full_name, create=True)
        return deck_id
