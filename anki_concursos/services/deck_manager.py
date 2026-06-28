import logging
from aqt import mw

logger = logging.getLogger("anki_concursos.services.deck")

class DeckManager:
    def deck_exists(self, deck_id: int) -> bool:
        """Return whether an Anki deck id still exists in the collection."""
        if not mw or not getattr(mw, "col", None):
            return False
        try:
            return mw.col.decks.get(deck_id) is not None
        except Exception:
            return False

    def ensure_deck(self, name: str) -> int:
        """Create deck 'Anki Concursos::{name}' if it doesn't exist. Returns deck ID."""
        full_name = f"Anki Concursos::{name}"
        deck_id = mw.col.decks.id(full_name, create=True)
        return deck_id
