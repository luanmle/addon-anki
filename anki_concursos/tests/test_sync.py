import pytest
from unittest.mock import patch, MagicMock

from anki_concursos.sync.engine import SyncEngine
from anki_concursos.storage.models import RemoteDeck, RemoteCard, SyncLogEntry
from anki_concursos.api.client import ApiError

class MockQueryOp:
    def __init__(self, parent, op, success):
        self.op = op
        self.success = success
        self._failure_cb = None

    def failure(self, cb):
        self._failure_cb = cb
        return self

    def with_progress(self, msg):
        return self

    def run_in_background(self):
        try:
            result = self.op(None)
            self.success(result)
        except Exception as e:
            if self._failure_cb:
                self._failure_cb(e)
            else:
                raise e

@pytest.fixture
def mock_sync_setup():
    with patch("anki_concursos.sync.engine.QueryOp", MockQueryOp), \
         patch("anki_concursos.sync.engine.mw") as mock_mw:
        
        api = MagicMock()
        db = MagicMock()
        db.get_card.return_value = None
        
        # Mock status API
        api.get_addon_status.return_value = {"min_addon_version": "0.1.0"}
        
        engine = SyncEngine(api, db)
        
        # Mock the managers to prevent accessing Anki/filesystem databases
        engine.nt_manager = MagicMock()
        engine.note_manager = MagicMock()
        engine.note_manager.find_note_by_card_id.return_value = None
        engine.backup_manager = MagicMock()
        
        yield engine, api, db, mock_mw

def test_sync_version_incompatibility(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    # Require 0.2.0, but we are 0.1.0
    api.get_addon_status.return_value = {"min_addon_version": "0.2.0"}
    
    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    assert len(callback_called) == 1
    success, msg = callback_called[0]
    assert success is False
    assert "Sua versão do add-on" in msg
    assert "obsoleta" in msg

def test_sync_no_changes(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    
    # Setup mock returns
    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {}
    
    sync_resp = MagicMock()
    sync_resp.has_changes = False
    sync_resp.changes = []
    
    api.get_deck_manifest.return_value = manifest
    api.sync_deck_all_pages.return_value = sync_resp
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    assert len(callback_called) == 1
    assert callback_called[0] == (True, "Already up to date.")

def test_sync_apply_changes(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    
    # Mock Manifest
    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {
            "note_type": "nt",
            "fields": ["Front", "Back", "Answer", "Explanation"],
            "field_mapping": {"Front": "front_text", "Back": "back_text"}
        }
    }
    api.get_deck_manifest.return_value = manifest
    
    # Mock Changes: added, updated, removed, deprecated
    c_added = MagicMock(action="added", card_kind="basic", card_id="c_add", public_id="P1", new_card_version_id="v1", tags=[], fields={"front_text": "Q1", "back_text": "R1"})
    c_updated = MagicMock(action="updated", card_kind="basic", card_id="c_upd", public_id="P2", new_card_version_id="v2", tags=[], fields={"front_text": "Q2", "back_text": "R2"})
    c_removed = MagicMock(action="removed", card_kind="basic", card_id="c_rem", public_id="P3", new_card_version_id="v2", tags=[], fields=None)
    c_deprecated = MagicMock(action="deprecated", card_kind="basic", card_id="c_dep", public_id="P4", new_card_version_id="v2", tags=[], fields=None)
    
    sync_resp = MagicMock()
    sync_resp.from_release = 0
    sync_resp.to_release = 10
    sync_resp.has_changes = True
    sync_resp.changes = [c_added, c_updated, c_removed, c_deprecated]
    api.sync_deck_all_pages.return_value = sync_resp
    
    # Mock database responses for current state of cards
    db.get_card.side_effect = lambda cid: {
        "c_upd": RemoteCard("c_upd", "P2", "v1", "d1", 200, "basic", None, "active", "2026", "2026"),
        "c_rem": RemoteCard("c_rem", "P3", "v1", "d1", 300, "basic", None, "active", "2026", "2026"),
        "c_dep": RemoteCard("c_dep", "P4", "v1", "d1", 400, "basic", None, "active", "2026", "2026")
    }.get(cid)
    
    # Mock note manager returning a mock note id for creation
    engine.note_manager.create_note.return_value = 100
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Assertions on NoteManager calls
    engine.note_manager.create_note.assert_called_once_with(
        deck_id=123,
        note_type_name="nt",
        public_id="P1",
        card_id="c_add",
        version_id="v1",
        tags=[],
        fields={"front_text": "Q1", "back_text": "R1"},
        field_mapping={"Front": "front_text", "Back": "back_text"}
    )
    
    engine.note_manager.update_note.assert_called_once_with(
        anki_note_id=200,
        version_id="v2",
        fields={"front_text": "Q2", "back_text": "R2"},
        field_mapping={"Front": "front_text", "Back": "back_text"}
    )
    
    engine.note_manager.suspend_note.assert_called_once_with(300)
    engine.note_manager.deprecate_note.assert_called_once_with(400)
    
    # Assertions on DB calls
    assert db.upsert_card.call_count == 4
    called_cards = [args[0][0] for args in db.upsert_card.call_args_list]
    card_map = {c.card_id: c for c in called_cards}
    
    assert card_map["c_add"].status == "active"
    assert card_map["c_add"].card_version_id == "v1"
    assert card_map["c_add"].anki_note_id == 100
    
    assert card_map["c_upd"].status == "active"
    assert card_map["c_upd"].card_version_id == "v2"
    assert card_map["c_upd"].anki_note_id == 200
    
    assert card_map["c_rem"].status == "removed"
    assert card_map["c_rem"].card_version_id == "v2"
    assert card_map["c_rem"].anki_note_id == 300
    
    assert card_map["c_dep"].status == "deprecated"
    assert card_map["c_dep"].card_version_id == "v2"
    assert card_map["c_dep"].anki_note_id == 400
    
    db.upsert_deck.assert_called_once()
    db.add_sync_log.assert_called_once()
    
    assert callback_called == [(True, "Successfully synced 4 changes.")]

def test_sync_engine_rollback_on_error(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    
    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest
    
    # An added card that will fail during note creation
    c_added = MagicMock(action="added", card_kind="basic", card_id="c1", public_id="P1", new_card_version_id="v1", tags=[], fields={"Front": "Q1"})
    sync_resp = MagicMock()
    sync_resp.changes = [c_added]
    api.sync_deck_all_pages.return_value = sync_resp
    
    # Simulate exception during creation
    engine.note_manager.create_note.side_effect = RuntimeError("Anki Database Lock Error")
    engine.backup_manager.create_backup.return_value = "backup_file_path"
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Check that backup was created and restored
    engine.backup_manager.create_backup.assert_called_once()
    engine.backup_manager.restore_backup.assert_called_once_with("backup_file_path")
    
    assert len(callback_called) == 1
    success, msg = callback_called[0]
    assert success is False
    assert "Rollback" in msg or "rolled back" in msg
    assert "Anki Database Lock Error" in msg


def test_sync_status_404_success(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    
    # Mock status endpoint returning empty dict (simulating handled 404)
    api.get_addon_status.return_value = {}
    
    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {}
    api.get_deck_manifest.return_value = manifest
    
    sync_resp = MagicMock()
    sync_resp.has_changes = False
    sync_resp.changes = []
    api.sync_deck_all_pages.return_value = sync_resp
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Should complete successfully
    assert len(callback_called) == 1
    assert callback_called[0] == (True, "Already up to date.")


def test_sync_prevent_duplicate_by_card_id(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    
    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {
            "note_type": "nt",
            "fields": ["Front", "Back"],
            "field_mapping": {"Front": "front_text", "Back": "back_text"}
        }
    }
    api.get_deck_manifest.return_value = manifest
    
    # An "added" card from sync, but it already exists in Anki with note ID 500
    c_added = MagicMock(action="added", card_kind="basic", card_id="c_dup_test", public_id="P_dup", new_card_version_id="v_new", tags=[], fields={"front_text": "Updated Front", "back_text": "Updated Back"})
    sync_resp = MagicMock()
    sync_resp.has_changes = True
    sync_resp.changes = [c_added]
    api.sync_deck_all_pages.return_value = sync_resp
    
    # Mock find_note_by_card_id to return the existing Anki note ID 500
    engine.note_manager.find_note_by_card_id.return_value = 500
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Verify we did NOT call create_note, but called update_note on the existing note ID 500
    engine.note_manager.create_note.assert_not_called()
    engine.note_manager.update_note.assert_called_once_with(
        anki_note_id=500,
        version_id="v_new",
        fields={"front_text": "Updated Front", "back_text": "Updated Back"},
        field_mapping={"Front": "front_text", "Back": "back_text"}
    )
    
    # Verify the local SQLite DB mapping is correctly established/saved
    db.upsert_card.assert_called_once()
    saved_card = db.upsert_card.call_args[0][0]
    assert saved_card.card_id == "c_dup_test"
    assert saved_card.anki_note_id == 500
    assert saved_card.status == "active"
    
    assert callback_called == [(True, "Successfully synced 1 changes.")]
