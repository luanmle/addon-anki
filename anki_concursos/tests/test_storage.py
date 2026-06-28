from anki_concursos.storage.models import RemoteDeck, RemoteCard, SyncLogEntry
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

def test_delete_deck_removes_sync_log(temp_db):
    now = datetime.now(timezone.utc).isoformat()
    temp_db.upsert_deck(RemoteDeck("d1", "Deck", 1, "nt", 1, now, now, now))
    temp_db.add_sync_log(SyncLogEntry(
        deck_id="d1",
        from_release=0,
        to_release=1,
        cards_added=1,
        cards_updated=0,
        cards_removed=0,
        cards_deprecated=0,
        synced_at=now,
        duration_ms=None,
        success=True,
        error_message=None,
    ))

    temp_db.delete_deck("d1")

    assert temp_db.get_deck("d1") is None
    with temp_db.transaction() as c:
        c.execute("SELECT COUNT(*) FROM sync_log WHERE deck_id = ?", ("d1",))
        assert c.fetchone()[0] == 0


def test_get_sync_logs_returns_latest_first(temp_db):
    now = datetime.now(timezone.utc).isoformat()
    temp_db.upsert_deck(RemoteDeck("d1", "Deck", 1, "nt", 2, now, now, now))
    temp_db.add_sync_log(SyncLogEntry(
        deck_id="d1",
        from_release=0,
        to_release=1,
        cards_added=1,
        cards_updated=0,
        cards_removed=0,
        cards_deprecated=0,
        synced_at=now,
        duration_ms=None,
        success=True,
        error_message=None,
    ))
    temp_db.add_sync_log(SyncLogEntry(
        deck_id="d1",
        from_release=1,
        to_release=2,
        cards_added=0,
        cards_updated=1,
        cards_removed=0,
        cards_deprecated=0,
        synced_at=now,
        duration_ms=None,
        success=False,
        error_message="erro",
    ))

    logs = temp_db.get_sync_logs("d1")

    assert [log.to_release for log in logs] == [2, 1]
    assert logs[0].success is False
    assert logs[0].error_message == "erro"


def test_repair_integrity_removes_orphan_metadata(temp_db):
    now = datetime.now(timezone.utc).isoformat()
    with temp_db.transaction() as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("""
            INSERT INTO remote_cards
            (card_id, public_id, card_version_id, deck_id, anki_note_id, card_kind, content_hash, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("c1", "P1", "v1", "missing", 123, "basic", None, "active", now, now))
        c.execute("""
            INSERT INTO sync_log
            (deck_id, from_release, to_release, cards_added, cards_updated, cards_removed,
             cards_deprecated, synced_at, duration_ms, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("missing", 0, 1, 1, 0, 0, 0, now, None, 1, None))
        c.execute("PRAGMA foreign_keys = ON")

    assert temp_db.repair_integrity() == 2

    with temp_db.transaction() as c:
        c.execute("SELECT COUNT(*) FROM remote_cards")
        assert c.fetchone()[0] == 0
        c.execute("SELECT COUNT(*) FROM sync_log")
        assert c.fetchone()[0] == 0

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
        updated_at=now,
        remote_fields={"Front": "Pergunta", "Back": "Resposta"},
    )
    temp_db.upsert_card(card)
    
    saved = temp_db.get_card("c1")
    assert saved.public_id == "AC-123"
    assert saved.remote_fields == {"Front": "Pergunta", "Back": "Resposta"}
    
    temp_db.update_card_status("c1", "deprecated", "v2")
    updated = temp_db.get_card("c1")
    assert updated.status == "deprecated"
    assert updated.card_version_id == "v2"
