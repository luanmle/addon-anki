import importlib
import sys
from unittest.mock import MagicMock, patch

from anki_concursos.api.models import (
    AnkiDeckReleaseListResponse,
    AnkiDeckReleaseSummaryResponse,
)
from anki_concursos.storage.models import RemoteDeck, SyncLogEntry


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
            self.success(self.op(None))
        except Exception as exc:
            self._failure_cb(exc)


def _import_status_dialog():
    qt = sys.modules["aqt.qt"]
    qt.__all__ = [
        "QDialog",
        "QMessageBox",
        "QTableWidget",
        "QTableWidgetItem",
        "QHeaderView",
        "QVBoxLayout",
        "QHBoxLayout",
        "QPushButton",
        "QLabel",
    ]

    class DialogBase:
        def __init__(self, *args, **kwargs):
            pass

        def setWindowTitle(self, *args, **kwargs):
            pass

        def resize(self, *args, **kwargs):
            pass

        def accept(self):
            pass

    qt.QDialog = DialogBase
    qt.QMessageBox = MagicMock()
    qt.QTableWidget = MagicMock()
    qt.QTableWidgetItem = MagicMock()
    qt.QHeaderView = MagicMock()
    qt.QHeaderView.ResizeMode = MagicMock(Stretch=1)
    qt.QVBoxLayout = MagicMock()
    qt.QHBoxLayout = MagicMock()
    qt.QPushButton = MagicMock()
    qt.QLabel = MagicMock()

    sys.modules.pop("anki_concursos.gui.status_dialog", None)
    gui_pkg = sys.modules.get("anki_concursos.gui")
    if gui_pkg and hasattr(gui_pkg, "status_dialog"):
        delattr(gui_pkg, "status_dialog")
    return importlib.import_module("anki_concursos.gui.status_dialog")


def test_history_uses_remote_releases_when_available():
    module = _import_status_dialog()
    api = MagicMock()
    db = MagicMock()
    api.list_subscriptions.return_value = MagicMock(items=[])
    api.get_deck_releases.return_value = AnkiDeckReleaseListResponse(
        deck_id="d1",
        latest_release=2,
        items=[
            AnkiDeckReleaseSummaryResponse(
                release_id="r2",
                release_number=2,
                published_at="2026-06-26T10:20:00Z",
                summary="Correções",
                cards_added=1,
                cards_updated=2,
                cards_removed=3,
                cards_deprecated=4,
            )
        ],
        page=1,
        page_size=20,
        total=1,
        pages=1,
    )

    with patch("anki_concursos.gui.status_dialog.QueryOp", MockQueryOp), \
         patch("anki_concursos.gui.status_dialog.QMessageBox") as msgbox:
        dialog = module.StatusDialog(api, db)
        dialog.on_history("d1", "Deck 1")

        msg = msgbox.information.call_args[0][2]
        assert "Release mais recente: 2" in msg
        assert "Release 2 | 2026-06-26 10:20" in msg
        assert "Correções" in msg
        assert "+1 ~2 -3 dep.4" in msg


def test_history_falls_back_to_local_when_remote_fails():
    module = _import_status_dialog()
    api = MagicMock()
    db = MagicMock()
    api.list_subscriptions.return_value = MagicMock(items=[])
    api.get_deck_releases.side_effect = RuntimeError("remote down")
    db.get_deck.return_value = RemoteDeck("d1", "Deck 1", 1, "nt", 2, None, "2026", "2026")
    db.get_sync_logs.return_value = [
        SyncLogEntry(
            deck_id="d1",
            from_release=1,
            to_release=2,
            cards_added=0,
            cards_updated=1,
            cards_removed=0,
            cards_deprecated=0,
            synced_at="2026-06-26T11:30:00Z",
            duration_ms=None,
            success=True,
            error_message=None,
        )
    ]

    with patch("anki_concursos.gui.status_dialog.QueryOp", MockQueryOp), \
         patch("anki_concursos.gui.status_dialog.QMessageBox") as msgbox:
        dialog = module.StatusDialog(api, db)
        dialog.on_history("d1", "Deck 1")

        msg = msgbox.information.call_args[0][2]
        assert "Histórico remoto indisponível" in msg
        assert "release 1 -> 2" in msg
        assert "+0 ~1 -0 dep.0" in msg
