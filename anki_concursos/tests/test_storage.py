from anki_concursos.storage.models import RemoteDeck, RemoteCard
from datetime import datetime, timezone

def test_deck_crud(temp_db):
    now = datetime.now(timezone.utc).isoformat()
    deck = RemoteDeck(
        deck_id="uuid-1",
        deck_name="Test Deck",
        anki_deck_id=123,
        note_type_name="Basic",
        latest_release=10,
        last_sync=now,
        created_at=now,
        updated_at=now
    )
    
    temp_db.upsert_deck(deck)
    saved = temp_db.get_deck("uuid-1")
    assert saved.deck_name == "Test Deck"
    
    deck.deck_name = "Updated Deck"
    temp_db.upsert_deck(deck)
    assert temp_db.get_deck("uuid-1").deck_name == "Updated Deck"
    
    assert len(temp_db.get_all_decks()) == 1
    
    temp_db.delete_deck("uuid-1")
    assert temp_db.get_deck("uuid-1") is None

def test_card_crud(temp_db):
    now = datetime.now(timezone.utc).isoformat()
    # Need a deck first for FK
    temp_db.upsert_deck(RemoteDeck("d1", "Deck", 1, "nt", 0, now, now, now))
    
    card = RemoteCard(
        card_id="c1",
        public_id="AC-123",
        card_version_id="v1",
        deck_id="d1",
        anki_note_id=456,
        card_kind="basic",
        content_hash=None,
        status="active",
        created_at=now,
        updated_at=now
    )
    temp_db.upsert_card(card)
    
    saved = temp_db.get_card("c1")
    assert saved.public_id == "AC-123"
    
    temp_db.update_card_status("c1", "deprecated", "v2")
    updated = temp_db.get_card("c1")
    assert updated.status == "deprecated"
    assert updated.card_version_id == "v2"
