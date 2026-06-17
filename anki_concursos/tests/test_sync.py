import pytest
from unittest.mock import patch, MagicMock

from anki_concursos.sync.engine import SyncEngine
from anki_concursos.storage.models import RemoteDeck, RemoteCard, SyncLogEntry

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
        
        # Mock status API
        api.get_addon_status.return_value = {"min_addon_version": "0.1.0"}
        
        engine = SyncEngine(api, db)
        
        # Mock the managers to prevent accessing Anki/filesystem databases
        engine.nt_manager = MagicMock()
        engine.note_manager = MagicMock()
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
    db.upsert_card.assert_called()
    db.update_card_status.assert_any_call("c_upd", "active", "v2")
    db.update_card_status.assert_any_call("c_rem", "removed", "v2")
    db.update_card_status.assert_any_call("c_dep", "deprecated", "v2")
    
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
