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
        db.repair_integrity.return_value = 0
        db.get_card.return_value = None
        db.repair_integrity.return_value = 0
        
        # Mock status API
        api.get_addon_status.return_value = {"min_addon_version": "0.1.0"}
        api.list_subscriptions.return_value = MagicMock(
            items=[MagicMock(deck_id="d1", unsubscribed_at=None)]
        )
        
        engine = SyncEngine(api, db)
        
        # Mock the managers to prevent accessing Anki/filesystem databases
        engine.nt_manager = MagicMock()
        engine.note_manager = MagicMock()
        engine.note_manager.note_exists.return_value = True
        engine.note_manager.note_modified_after.return_value = False
        engine.note_manager.find_note_ids_by_card_id.return_value = []
        engine.note_manager.find_note_by_card_id.return_value = None
        engine._deck_exists = MagicMock(return_value=True)
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
    
    db.repair_integrity.assert_called_once()
    assert len(callback_called) == 1
    assert callback_called[0] == (True, "Tudo atualizado.")


def test_sync_reports_local_integrity_repair(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    db.repair_integrity.return_value = 2

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {}
    api.get_deck_manifest.return_value = manifest

    sync_resp = MagicMock()
    sync_resp.has_changes = False
    sync_resp.changes = []
    sync_resp.to_release = 0
    api.sync_deck_all_pages.return_value = sync_resp
    api.get_deck_state.return_value = None

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    assert callback_called == [(True, "🧰 Reparadas 2 linhas de metadados locais de sync.")]

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
    
    assert callback_called == [(True, "🔄 Sincronizadas 4 alterações.")]


def test_sync_native_manifest_fields_are_applied_without_legacy_mapping(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "Meu Modelo Customizado"
    manifest.templates = [
        {
            "template_name": "Card 1",
            "note_type": "Meu Modelo Customizado",
            "card_kind": "basic",
            "fields": ["Enunciado", "Alternativas", "Comentario"],
            "front_html": "{{Enunciado}}",
            "back_html": "{{FrontSide}}\n\n{{Comentario}}",
            "styling_css": "",
        }
    ]
    manifest.supported_note_types = {
        "basic": {
            "note_type": "Anki Concursos Basic",
            "fields": ["Front", "Back"],
            "field_mapping": {"Front": "front_text", "Back": "back_text"},
        }
    }
    api.get_deck_manifest.return_value = manifest

    c_added = MagicMock(
        action="added",
        card_kind="basic",
        card_id="c_native",
        public_id="P_native",
        new_card_version_id="v1",
        tags=[],
        fields={
            "Enunciado": "Julgue o item.",
            "Alternativas": "Certo ou errado",
            "Comentario": "Comentario livre.",
        },
        note_type="Meu Modelo Customizado",
        template_name="Card 1",
        template=None,
    )
    sync_resp = MagicMock(
        has_changes=True,
        changes=[c_added],
        from_release=0,
        to_release=1,
    )
    api.sync_deck_all_pages.return_value = sync_resp
    engine.note_manager.create_note.return_value = 100

    callback_called = []

    def callback(success, message):
        callback_called.append((success, message))

    engine.sync_all(callback)

    engine.note_manager.create_note.assert_called_once_with(
        deck_id=123,
        note_type_name="Meu Modelo Customizado",
        public_id="P_native",
        card_id="c_native",
        version_id="v1",
        tags=[],
        fields={
            "Enunciado": "Julgue o item.",
            "Alternativas": "Certo ou errado",
            "Comentario": "Comentario livre.",
        },
        field_mapping=None,
    )
    assert callback_called == [(True, "🔄 Sincronizadas 1 alteração.")]


def test_sync_update_preserves_protected_fields_from_manifest(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.templates = []
    manifest.protected_fields = []
    manifest.supported_note_types = {
        "basic": {
            "note_type": "nt",
            "fields": ["Front", "Back"],
            "field_mapping": {"Front": "front_text", "Back": "back_text"},
            "protected_fields": ["front_text"],
        }
    }
    api.get_deck_manifest.return_value = manifest

    c_updated = MagicMock(
        action="updated",
        card_kind="basic",
        card_id="c_upd",
        public_id="P2",
        new_card_version_id="v2",
        tags=[],
        fields={"front_text": "Remote front", "back_text": "Remote back"},
        content_hash="NEW",
    )
    sync_resp = MagicMock(
        has_changes=True,
        changes=[c_updated],
        from_release=0,
        to_release=1,
    )
    api.sync_deck_all_pages.return_value = sync_resp
    db.get_card.return_value = RemoteCard(
        "c_upd", "P2", "v1", "d1", 200, "basic", "OLD", "active", "2026", "2026"
    )

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    engine.note_manager.update_note.assert_called_once_with(
        anki_note_id=200,
        version_id="v2",
        fields={"front_text": "Remote front", "back_text": "Remote back"},
        field_mapping={"Front": "front_text", "Back": "back_text"},
        protected_fields={"front_text", "Front"},
    )
    assert callback_called == [(True, "🔄 Sincronizadas 1 alteração.")]

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
    assert "restaurado" in msg
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
    assert callback_called[0] == (True, "Tudo atualizado.")


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
    engine.note_manager.find_note_ids_by_card_id.return_value = [500]
    
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
    
    assert callback_called == [(True, "🔄 Sincronizadas 1 alteração.")]


def test_sync_warns_when_card_id_has_duplicate_notes(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {
            "note_type": "nt",
            "fields": ["Front"],
            "field_mapping": {},
        }
    }
    api.get_deck_manifest.return_value = manifest

    c_added = MagicMock(
        action="added",
        card_kind="basic",
        card_id="c_dup",
        public_id="P_dup",
        new_card_version_id="v1",
        tags=[],
        fields={"Front": "Q1"},
        template=None,
        content_hash="HASH",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_added], from_release=0, to_release=1)
    api.sync_deck_all_pages.return_value = sync_resp
    engine.note_manager.find_note_ids_by_card_id.return_value = [500, 501]

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    engine.note_manager.update_note.assert_called_once_with(
        anki_note_id=500,
        version_id="v1",
        fields={"Front": "Q1"},
        field_mapping={},
    )
    assert callback_called == [
        (
            True,
            "🔄 Sincronizadas 1 alteração.\n⚠️ Encontradas notas locais duplicadas para 1 Card ID: c_dup.",
        )
    ]


def test_sync_bootstrap_no_subscriptions(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    db.get_all_decks.return_value = []
    api.list_subscriptions.return_value = MagicMock(items=[])
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    assert callback_called == [(True, "Nenhum baralho instalado para sincronizar.")]


def test_sync_bootstrap_with_subscriptions(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    
    db.get_all_decks.return_value = []
    engine._ensure_deck = MagicMock(return_value=123)
    
    # Mock active subscription
    sub = MagicMock(deck_id="d_sub", unsubscribed_at=None)
    api.list_subscriptions.return_value = MagicMock(items=[sub])
    db.get_deck.return_value = None
    
    # Mock manifest
    manifest = MagicMock()
    manifest.name = "Sub Deck"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {
            "note_type": "nt",
            "fields": ["Front"],
            "field_mapping": {"Front": "front_text"}
        }
    }
    api.get_deck_manifest.return_value = manifest
    
    # Mock sync response (since_release=0 bootstrap)
    c_added = MagicMock(
        action="added",
        card_kind="basic",
        card_id="c_boot",
        public_id="P_boot",
        new_card_version_id="v1",
        tags=[],
        fields={"front_text": "Bootstrap front"},
        template=None
    )
    sync_resp = MagicMock(to_release=5, changes=[c_added])
    api.sync_deck_all_pages.return_value = sync_resp
    
    # Mock Anki note creation return
    engine.note_manager.create_note.return_value = 600
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Verify Anki API calls
    api.list_subscriptions.assert_called_once()
    api.get_deck_manifest.assert_called_once_with("d_sub")
    api.sync_deck_all_pages.assert_called_once_with("d_sub", since_release=0)
    
    # Verify note creation & DB insertions
    engine.note_manager.create_note.assert_called_once_with(
        deck_id=123,
        note_type_name="nt",
        public_id="P_boot",
        card_id="c_boot",
        version_id="v1",
        tags=[],
        fields={"front_text": "Bootstrap front"},
        field_mapping={"Front": "front_text"}
    )
    db.upsert_deck.assert_called_once()
    db.upsert_card.assert_called_once()
    db.add_sync_log.assert_called_once()
    
    assert len(callback_called) == 1
    assert "Instalado 1 baralho inscrito" in callback_called[0][1]


def test_sync_installs_new_subscription_when_other_decks_exist(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    installed_deck = RemoteDeck("d1", "Deck 1", 123, "nt", 1, None, "2026", "2026")
    db.get_all_decks.return_value = [installed_deck]
    engine._ensure_deck = MagicMock(return_value=456)

    sub_existing = MagicMock(deck_id="d1", unsubscribed_at=None)
    sub_new = MagicMock(deck_id="d2", unsubscribed_at=None)
    api.list_subscriptions.return_value = MagicMock(items=[sub_existing, sub_new])
    db.get_deck.side_effect = lambda deck_id: installed_deck if deck_id == "d1" else None

    installed_manifest = MagicMock()
    installed_manifest.name = "Deck 1"
    installed_manifest.note_type = "nt"
    installed_manifest.supported_note_types = {}

    new_manifest = MagicMock()
    new_manifest.name = "Deck 2"
    new_manifest.note_type = "nt"
    new_manifest.supported_note_types = {
        "basic": {
            "note_type": "nt",
            "fields": ["Front"],
            "field_mapping": {"Front": "front_text"},
        }
    }

    api.get_deck_manifest.side_effect = [installed_manifest, new_manifest]

    installed_sync = MagicMock(has_changes=False, changes=[], from_release=1, to_release=1)
    new_change = MagicMock(
        action="added",
        card_kind="basic",
        card_id="c_new",
        public_id="P_new",
        new_card_version_id="v1",
        tags=[],
        fields={"front_text": "Nova pergunta"},
        template=None,
    )
    new_sync = MagicMock(to_release=3, changes=[new_change])
    api.sync_deck_all_pages.side_effect = [installed_sync, new_sync]
    engine.note_manager.create_note.return_value = 900

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    api.list_subscriptions.assert_called_once()
    api.sync_deck_all_pages.assert_any_call("d1", since_release=1)
    api.sync_deck_all_pages.assert_any_call("d2", since_release=0)
    engine.note_manager.create_note.assert_called_once_with(
        deck_id=456,
        note_type_name="nt",
        public_id="P_new",
        card_id="c_new",
        version_id="v1",
        tags=[],
        fields={"front_text": "Nova pergunta"},
        field_mapping={"Front": "front_text"},
    )
    assert callback_called == [
        (True, "📥 Instalado 1 baralho inscrito: Deck 2.\n🔄 Sincronizadas 1 alteração.")
    ]


def test_sync_forgets_local_deck_without_active_subscription(mock_sync_setup):
    """I4: empty subscriptions with local decks present = suspicious; skip cleanup."""
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    api.list_subscriptions.return_value = MagicMock(items=[])

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    # Empty subscription response with local decks present is treated as
    # transient/suspicious — no decks are deleted this run.
    db.delete_deck.assert_not_called()
    api.get_deck_manifest.assert_not_called()
    api.sync_deck_all_pages.assert_not_called()
    assert callback_called == [(True, "Tudo atualizado.")]


def test_sync_invalid_delta_action(mock_sync_setup):
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
    
    # Mock delta with invalid action
    c_invalid = MagicMock(
        action="invalid_action",
        card_kind="basic",
        card_id="c_inv",
        public_id="P1",
        new_card_version_id="v1",
        tags=[],
        fields={"Front": "Val"}
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_invalid], from_release=0, to_release=1)
    api.sync_deck_all_pages.return_value = sync_resp
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Verify no note manager action was invoked
    engine.note_manager.create_note.assert_not_called()
    engine.note_manager.update_note.assert_not_called()
    engine.note_manager.suspend_note.assert_not_called()
    engine.note_manager.deprecate_note.assert_not_called()
    db.upsert_card.assert_not_called()
    
    # But sync finishes successfully (with 0 stats in log)
    assert callback_called == [(True, "🔄 Sincronizadas 1 alteração.")]
    db.add_sync_log.assert_called_once()
    log = db.add_sync_log.call_args[0][0]
    assert log.cards_added == 0
    assert log.cards_updated == 0
    assert log.cards_removed == 0
    assert log.cards_deprecated == 0


def test_sync_invalid_delta_missing_fields(mock_sync_setup):
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
    
    # Mock delta with missing fields for added/updated
    c_added = MagicMock(action="added", card_kind="basic", card_id="c_add", public_id="P1", fields=None)
    c_updated = MagicMock(action="updated", card_kind="basic", card_id="c_upd", public_id="P2", fields=None)
    
    sync_resp = MagicMock(has_changes=True, changes=[c_added, c_updated], from_release=0, to_release=1)
    api.sync_deck_all_pages.return_value = sync_resp
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Verify note manager was not called to create/update
    engine.note_manager.create_note.assert_not_called()
    engine.note_manager.update_note.assert_not_called()
    db.upsert_card.assert_not_called()
    
    assert callback_called == [(True, "🔄 Sincronizadas 2 alterações.")]


def test_sync_missing_public_id(mock_sync_setup):
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
    
    # Added card but missing public_id (None)
    c_added = MagicMock(
        action="added",
        card_kind="basic",
        card_id="c_add",
        public_id=None,
        new_card_version_id="v1",
        tags=[],
        fields={"Front": "Val"}
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_added], from_release=0, to_release=1)
    api.sync_deck_all_pages.return_value = sync_resp
    
    # Make create_note raise an error if public_id is None
    def mock_create_note(*args, **kwargs):
        pub_id = kwargs.get("public_id")
        if pub_id is None:
            raise ValueError("Public ID is required")
        return 700
    engine.note_manager.create_note.side_effect = mock_create_note
    engine.backup_manager.create_backup.return_value = "backup_file"
    
    callback_called = []
    def callback(success, message):
        callback_called.append((success, message))
        
    engine.sync_all(callback)
    
    # Assert rollback was executed
    engine.backup_manager.create_backup.assert_called_once()
    engine.backup_manager.restore_backup.assert_called_once_with("backup_file")
    
    assert len(callback_called) == 1
    success, msg = callback_called[0]
    assert success is False
    assert "Public ID is required" in msg


def test_installer_install_deck_prevent_duplicate():
    from anki_concursos.sync.installer import DeckInstaller
    
    with patch("anki_concursos.sync.installer.QueryOp", MockQueryOp), \
         patch("anki_concursos.sync.installer.mw") as mock_mw:
        
        api = MagicMock()
        db = MagicMock()
        db.repair_integrity.return_value = 0
        
        manifest = MagicMock()
        manifest.name = "Sub Deck"
        manifest.note_type = "nt"
        manifest.supported_note_types = {
            "basic": {
                "note_type": "nt",
                "fields": ["Front"],
                "field_mapping": {"Front": "f1"}
            }
        }
        api.get_deck_manifest.return_value = manifest
        
        # added card that already exists in Anki
        c_added = MagicMock(
            action="added",
            card_kind="basic",
            card_id="c_dup",
            public_id="P_dup",
            new_card_version_id="v1",
            tags=[],
            fields={"f1": "Q1"},
            template=None,
            content_hash="HASH"
        )
        sync_resp = MagicMock(to_release=5, changes=[c_added])
        api.sync_deck_all_pages.return_value = sync_resp
        
        installer = DeckInstaller(api, db)
        installer.nt_manager = MagicMock()
        installer.deck_manager = MagicMock()
        installer.deck_manager.ensure_deck.return_value = 123
        installer.note_manager = MagicMock()
        
        # Simulate Anki note ID 888 already exists for this card_id
        installer.note_manager.find_note_ids_by_card_id.return_value = [888]
        
        callback_called = []
        def callback(success, message):
            callback_called.append((success, message))
            
        installer.install_deck("d_sub", callback)
        
        db.repair_integrity.assert_called_once()
        # Verify update_note was called instead of create_note
        installer.note_manager.create_note.assert_not_called()
        installer.note_manager.update_note.assert_called_once_with(
            anki_note_id=888,
            version_id="v1",
            fields={"f1": "Q1"},
            field_mapping={"Front": "f1"}
        )
        
        # Verify DB upsert
        db.upsert_card.assert_called_once()
        saved_card = db.upsert_card.call_args[0][0]
        assert saved_card.card_id == "c_dup"
        assert saved_card.anki_note_id == 888
        assert saved_card.content_hash == "HASH"
        
        assert callback_called == [(True, "Instalado 1 card com sucesso.")]


def test_installer_reports_local_integrity_repair():
    from anki_concursos.sync.installer import DeckInstaller

    with patch("anki_concursos.sync.installer.QueryOp", MockQueryOp), \
         patch("anki_concursos.sync.installer.mw"):

        api = MagicMock()
        db = MagicMock()
        db.repair_integrity.return_value = 1

        manifest = MagicMock()
        manifest.name = "Sub Deck"
        manifest.note_type = "nt"
        manifest.supported_note_types = {}
        api.get_deck_manifest.return_value = manifest
        api.sync_deck_all_pages.return_value = MagicMock(to_release=5, changes=[])

        installer = DeckInstaller(api, db)
        installer.nt_manager = MagicMock()
        installer.deck_manager = MagicMock()
        installer.deck_manager.ensure_deck.return_value = 123
        installer.note_manager = MagicMock()

        callback_called = []
        installer.install_deck("d_sub", lambda success, message: callback_called.append((success, message)))

        assert callback_called == [
            (True, "🧰 Reparadas 1 linha de metadados locais de sync.\nInstalados 0 cards com sucesso.")
        ]


def test_installer_warns_when_card_id_has_duplicate_notes():
    from anki_concursos.sync.installer import DeckInstaller

    with patch("anki_concursos.sync.installer.QueryOp", MockQueryOp), \
         patch("anki_concursos.sync.installer.mw"):

        api = MagicMock()
        db = MagicMock()
        db.repair_integrity.return_value = 0

        manifest = MagicMock()
        manifest.name = "Sub Deck"
        manifest.note_type = "nt"
        manifest.supported_note_types = {
            "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
        }
        api.get_deck_manifest.return_value = manifest

        c_added = MagicMock(
            action="added",
            card_kind="basic",
            card_id="c_dup",
            public_id="P_dup",
            new_card_version_id="v1",
            tags=[],
            fields={"Front": "Q1"},
            template=None,
            content_hash="HASH",
        )
        api.sync_deck_all_pages.return_value = MagicMock(to_release=5, changes=[c_added])

        installer = DeckInstaller(api, db)
        installer.nt_manager = MagicMock()
        installer.deck_manager = MagicMock()
        installer.deck_manager.ensure_deck.return_value = 123
        installer.note_manager = MagicMock()
        installer.note_manager.find_note_ids_by_card_id.return_value = [888, 999]

        callback_called = []
        installer.install_deck("d_sub", lambda success, message: callback_called.append((success, message)))

        installer.note_manager.update_note.assert_called_once_with(
            anki_note_id=888,
            version_id="v1",
            fields={"Front": "Q1"},
            field_mapping={},
        )
        assert callback_called == [
            (
                True,
                "Instalado 1 card com sucesso.\n⚠️ Encontradas notas locais duplicadas para 1 Card ID: c_dup.",
            )
        ]


def test_version_is_outdated_handles_nonnumeric_and_padding():
    # Equal versions, including zero-padding of shorter strings.
    assert SyncEngine._version_is_outdated("0.1.0", "0.1.0") is False
    assert SyncEngine._version_is_outdated("0.1", "0.1.0") is False
    assert SyncEngine._version_is_outdated("1.0.0", "1.0") is False
    # Genuinely older.
    assert SyncEngine._version_is_outdated("0.1.0", "0.2.0") is True
    # Non-numeric segments must not raise; treated as 0.
    assert SyncEngine._version_is_outdated("0.1.0b1", "0.1.0") is False
    assert SyncEngine._version_is_outdated("0.1.0", "0.2.0-rc1") is True


def test_assert_version_supported_ignores_garbage_min_version(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup
    # A malformed server min version must be tolerated, not crash sync.
    engine._assert_version_supported({"min_addon_version": "not-a-version"})
    engine._assert_version_supported({})
    engine._assert_version_supported({"min_addon_version": None})


def test_sync_isolates_failed_deck_fetch(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck_fail = RemoteDeck("dfail", "Deck Fail", 1, "nt", 0, None, "2026", "2026")
    deck_ok = RemoteDeck("dok", "Deck OK", 2, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck_fail, deck_ok]
    db.get_card.return_value = None
    api.list_subscriptions.return_value = MagicMock(items=[
        MagicMock(deck_id="dfail", unsubscribed_at=None),
        MagicMock(deck_id="dok", unsubscribed_at=None),
    ])

    manifest = MagicMock()
    manifest.name = "Deck OK"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    # First deck's manifest fetch fails (e.g. 403 unsubscribed); second succeeds.
    api.get_deck_manifest.side_effect = [RuntimeError("403 Forbidden"), manifest]

    c_added = MagicMock(
        action="added",
        card_kind="basic",
        card_id="c1",
        public_id="P1",
        new_card_version_id="v1",
        tags=[],
        fields={"Front": "Q1"},
        template=None,
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_added], from_release=0, to_release=1)
    api.sync_deck_all_pages.return_value = sync_resp
    engine.note_manager.create_note.return_value = 700

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    # The healthy deck still applied despite the other deck failing to fetch.
    engine.note_manager.create_note.assert_called_once()
    assert len(callback_called) == 1
    success, msg = callback_called[0]
    assert success is True
    assert "Sincronizadas 1 alteração" in msg
    assert "Deck Fail" in msg


def test_sync_groups_collection_changes_into_one_undo(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 0, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    db.get_card.return_value = None

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    c_added = MagicMock(
        action="added", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v1", tags=[], fields={"Front": "Q1"}, template=None,
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_added], from_release=0, to_release=1)
    api.sync_deck_all_pages.return_value = sync_resp
    engine.note_manager.create_note.return_value = 700

    handle = object()
    mock_mw.col.add_custom_undo_entry.return_value = handle

    engine.sync_all(lambda *a: None)

    mock_mw.col.add_custom_undo_entry.assert_called_once()
    mock_mw.col.merge_undo_entries.assert_called_once_with(handle)


def test_sync_skips_write_when_content_hash_unchanged(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    # Card already tracked locally with the same content hash the server sends.
    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="HASH",
        status="active", created_at="2026", updated_at="2026",
    )

    c_added = MagicMock(
        action="added", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v1", tags=[], fields={"Front": "Q1"},
        template=None, content_hash="HASH",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_added], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    engine.sync_all(lambda *a: None)

    # Unchanged content => no collection write (avoids mod bump / AnkiWeb churn).
    engine.note_manager.update_note.assert_not_called()
    engine.note_manager.create_note.assert_not_called()
    # Tracking is still refreshed.
    db.upsert_card.assert_called_once()


def test_sync_writes_when_content_hash_differs(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026",
    )

    c_updated = MagicMock(
        action="updated", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields={"Front": "Q2"},
        template=None, content_hash="NEW",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_updated], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    engine.sync_all(lambda *a: None)

    engine.note_manager.update_note.assert_called_once()


def test_sync_aborts_before_overwriting_local_update_conflict(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026-06-26T10:00:00+00:00",
        remote_fields={"Front": "Q1"},
    )
    engine.note_manager.note_modified_after.return_value = True
    engine.note_manager.note_differs_from.return_value = True

    c_updated = MagicMock(
        action="updated", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields={"Front": "Q2"},
        template=None, content_hash="NEW",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_updated], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    assert callback_called[0][0] is False
    assert "Conflito local detectado" in callback_called[0][1]
    assert "Deck 1: P1" in callback_called[0][1]
    engine.note_manager.update_note.assert_not_called()
    db.upsert_deck.assert_not_called()
    db.add_sync_log.assert_not_called()
    engine.backup_manager.create_backup.assert_not_called()


def test_sync_pre_upgrade_card_without_baseline_does_not_block(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    # remote_fields=None → pre-upgrade card, no baseline to compare
    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026-06-26T10:00:00+00:00",
        remote_fields=None,
    )
    engine.note_manager.note_modified_after.return_value = True

    c_updated = MagicMock(
        action="updated", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields={"Front": "Q2"},
        template=None, content_hash="NEW",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_updated], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    assert callback_called[0][0] is True
    assert "Conflito local" not in callback_called[0][1]
    # no baseline → note_differs_from is never consulted
    engine.note_manager.note_differs_from.assert_not_called()


def test_sync_no_conflict_when_mod_bumped_but_content_unchanged(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026-06-26T10:00:00+00:00",
        remote_fields={"Front": "Q1"},
    )
    # mod bumped (e.g. tag edit) but tracked content unchanged
    engine.note_manager.note_modified_after.return_value = True
    engine.note_manager.note_differs_from.return_value = False

    c_updated = MagicMock(
        action="updated", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields={"Front": "Q2"},
        template=None, content_hash="NEW",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_updated], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    callback_called = []
    engine.sync_all(lambda success, message: callback_called.append((success, message)))

    assert callback_called[0][0] is True
    assert "Conflito local" not in callback_called[0][1]
    engine.note_manager.update_note.assert_called()


def test_sync_recreates_note_when_local_note_id_is_stale(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026",
    )
    engine.note_manager.note_exists.return_value = False
    engine.note_manager.find_note_ids_by_card_id.return_value = []
    engine.note_manager.find_note_by_card_id.return_value = None
    engine.note_manager.create_note.return_value = 900

    c_updated = MagicMock(
        action="updated", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields={"Front": "Q2"},
        template=None, content_hash="NEW",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_updated], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    engine.sync_all(lambda *a: None)

    engine.note_manager.update_note.assert_not_called()
    engine.note_manager.create_note.assert_called_once()
    saved_card = db.upsert_card.call_args_list[0][0][0]
    assert saved_card.anki_note_id == 900


def test_sync_marks_removed_when_local_note_id_is_stale(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026",
    )
    engine.note_manager.note_exists.return_value = False
    engine.note_manager.find_note_ids_by_card_id.return_value = []
    engine.note_manager.find_note_by_card_id.return_value = None

    c_removed = MagicMock(
        action="removed", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields=None,
        template=None, content_hash=None,
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_removed], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    engine.sync_all(lambda *a: None)

    engine.note_manager.suspend_note.assert_not_called()
    saved_card = db.upsert_card.call_args_list[0][0][0]
    assert saved_card.status == "removed"
    assert saved_card.anki_note_id is None


def test_sync_recreates_missing_local_deck_before_creating_note(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    db.get_card.return_value = None
    engine._deck_exists.return_value = False
    engine._ensure_deck = MagicMock(return_value=456)

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    c_added = MagicMock(
        action="added", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v1", tags=[], fields={"Front": "Q1"},
        template=None, content_hash="HASH",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_added], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp
    engine.note_manager.create_note.return_value = 900

    engine.sync_all(lambda *a: None)

    engine._ensure_deck.assert_called_once_with("Deck 1")
    engine.note_manager.create_note.assert_called_once_with(
        deck_id=456,
        note_type_name="nt",
        public_id="P1",
        card_id="c1",
        version_id="v1",
        tags=[],
        fields={"Front": "Q1"},
        field_mapping={},
    )
    saved_deck = db.upsert_deck.call_args_list[-1][0][0]
    assert saved_deck.anki_deck_id == 456


def _state(latest_release, *card_ids):
    from anki_concursos.api.models import AnkiDeckStateResponse, AnkiDeckStateCardResponse
    cards = [
        AnkiDeckStateCardResponse(card_id=cid, public_id=cid.upper(), card_version_id="v" + cid)
        for cid in card_ids
    ]
    return AnkiDeckStateResponse(
        deck_id="d1", latest_release=latest_release, total_active=len(cards), cards=cards
    )


def test_sync_reconciles_orphan_deletions(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 7, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]
    db.get_card.return_value = None

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {}
    api.get_deck_manifest.return_value = manifest

    # No content changes, but upstream dropped a card with no `removed` event.
    sync_resp = MagicMock(has_changes=False, changes=[], from_release=7, to_release=7)
    api.sync_deck_all_pages.return_value = sync_resp
    api.get_deck_state.return_value = _state(7, "keep")

    keep = RemoteCard("keep", "KEEP", "vkeep", "d1", 100, "basic", None, "active", "2026", "2026")
    orphan = RemoteCard("gone", "GONE", "vgone", "d1", 900, "basic", None, "active", "2026", "2026")
    db.get_active_cards_by_deck.return_value = [keep, orphan]

    msgs = []
    engine.sync_all(lambda s, m: msgs.append((s, m)))

    engine.note_manager.suspend_note.assert_called_once_with(900)
    removed = [
        call.args[0]
        for call in db.upsert_card.call_args_list
        if call.args[0].card_id == "gone"
    ]
    assert removed and removed[-1].status == "removed"
    assert msgs[0][0] is True
    assert "Reconciliado 1" in msgs[0][1]


def test_sync_failed_update_note_does_not_upsert_hash(mock_sync_setup):
    """C1: if update_note fails, the new hash must not be stored (card stays retryable)."""
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 5, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {
        "basic": {"note_type": "nt", "fields": ["Front"], "field_mapping": {}}
    }
    api.get_deck_manifest.return_value = manifest

    db.get_card.return_value = RemoteCard(
        card_id="c1", public_id="P1", card_version_id="v1", deck_id="d1",
        anki_note_id=500, card_kind="basic", content_hash="OLD",
        status="active", created_at="2026", updated_at="2026",
    )

    c_updated = MagicMock(
        action="updated", card_kind="basic", card_id="c1", public_id="P1",
        new_card_version_id="v2", tags=[], fields={"Front": "Q2"},
        template=None, content_hash="NEW",
    )
    sync_resp = MagicMock(has_changes=True, changes=[c_updated], from_release=5, to_release=6)
    api.sync_deck_all_pages.return_value = sync_resp

    # Simulate note write failure
    engine.note_manager.update_note.return_value = False

    engine.sync_all(lambda *a: None)

    # Failed write: hash must NOT be stored so the card is retried next sync.
    db.upsert_card.assert_not_called()


def test_sync_skips_reconcile_on_release_mismatch(mock_sync_setup):
    engine, api, db, mock_mw = mock_sync_setup

    deck = RemoteDeck("d1", "Deck 1", 123, "nt", 7, None, "2026", "2026")
    db.get_all_decks.return_value = [deck]

    manifest = MagicMock()
    manifest.name = "Deck 1"
    manifest.note_type = "nt"
    manifest.supported_note_types = {}
    api.get_deck_manifest.return_value = manifest

    sync_resp = MagicMock(has_changes=False, changes=[], from_release=7, to_release=7)
    api.sync_deck_all_pages.return_value = sync_resp
    # State pinned to a different release -> do not reconcile (avoid false deletes).
    api.get_deck_state.return_value = _state(6, "keep")

    db.get_active_cards_by_deck.return_value = [
        RemoteCard("gone", "GONE", "vg", "d1", 900, "basic", None, "active", "2026", "2026")
    ]

    msgs = []
    engine.sync_all(lambda s, m: msgs.append((s, m)))

    engine.note_manager.suspend_note.assert_not_called()
    assert msgs[0] == (True, "Tudo atualizado.")
