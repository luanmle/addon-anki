import sys
import importlib
from unittest.mock import MagicMock, patch


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


def _import_menu():
    qt = sys.modules["aqt.qt"]
    qt.__all__ = [
        "QDialog",
        "QMessageBox",
        "QAction",
        "QMenu",
    ]
    qt.QDialog = object
    qt.QMessageBox = MagicMock()
    qt.QAction = MagicMock()
    qt.QMenu = MagicMock()
    sys.modules.pop("anki_concursos.gui.login_dialog", None)
    sys.modules.pop("anki_concursos.gui.menu", None)
    gui_pkg = sys.modules.get("anki_concursos.gui")
    if gui_pkg and hasattr(gui_pkg, "menu"):
        delattr(gui_pkg, "menu")
    return importlib.import_module("anki_concursos.gui.menu")


def test_check_local_database_reports_no_repairs():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.QueryOp", MockQueryOp), \
         patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.QMessageBox") as msgbox:
        mock_mw.anki_concursos_db.repair_integrity.return_value = 0

        menu.on_check_local_database()

        mock_mw.anki_concursos_db.repair_integrity.assert_called_once()
        msgbox.information.assert_called_once_with(
            mock_mw,
            "Verificação do banco local",
            "Banco local de sync OK. Nenhum reparo necessário.",
        )


def test_check_local_database_reports_repairs():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.QueryOp", MockQueryOp), \
         patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.QMessageBox") as msgbox:
        mock_mw.anki_concursos_db.repair_integrity.return_value = 2

        menu.on_check_local_database()

        msgbox.information.assert_called_once_with(
            mock_mw,
            "Verificação do banco local",
            "🧰 Reparadas 2 linhas de metadados locais de sync.",
        )


def test_check_local_database_reports_failure():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.QueryOp", MockQueryOp), \
         patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.QMessageBox") as msgbox:
        mock_mw.anki_concursos_db.repair_integrity.side_effect = RuntimeError("bad db")

        menu.on_check_local_database()

        msgbox.critical.assert_called_once_with(
            mock_mw,
            "Falha na verificação do banco local",
            "bad db",
        )


def test_ensure_authenticated_returns_true_when_token_exists():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.LoginDialog") as login_dialog:
        mock_mw.anki_concursos_api.auth_service.get_token.return_value = "token"

        assert menu._ensure_authenticated() is True

        login_dialog.assert_not_called()


def test_ensure_authenticated_warns_when_login_cancelled():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.LoginDialog") as login_dialog, \
         patch("anki_concursos.gui.menu.QMessageBox") as msgbox:
        mock_mw.anki_concursos_api.auth_service.get_token.return_value = None

        assert menu._ensure_authenticated() is False

        login_dialog.assert_called_once_with(mock_mw.anki_concursos_api, mock_mw)
        login_dialog.return_value.exec.assert_called_once()
        msgbox.warning.assert_called_once_with(
            mock_mw,
            "Login necessário",
            "Faça login para usar esta ação.",
        )


def test_ensure_authenticated_returns_true_after_login_dialog_sets_token():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.LoginDialog") as login_dialog, \
         patch("anki_concursos.gui.menu.QMessageBox") as msgbox:
        mock_mw.anki_concursos_api.auth_service.get_token.side_effect = [None, "token", "token"]

        assert menu._ensure_authenticated() is True

        login_dialog.return_value.exec.assert_called_once()
        msgbox.warning.assert_not_called()


def test_refresh_menu_state_shows_login_when_logged_out():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.mw") as mock_mw:
        action = MagicMock()
        mock_mw.anki_concursos_login_action = action
        mock_mw.anki_concursos_api.auth_service.get_token.return_value = None

        menu.refresh_menu_state()

        action.setText.assert_called_once_with("Entrar")


def test_refresh_menu_state_shows_active_email_when_logged_in():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.mw") as mock_mw:
        action = MagicMock()
        mock_mw.anki_concursos_login_action = action
        mock_mw.anki_concursos_api.auth_service.get_token.return_value = "token"
        mock_mw.anki_concursos_api.auth_service.get_email.return_value = "user@example.com"

        menu.refresh_menu_state()

        action.setText.assert_called_once_with("Login ativo: user@example.com")


def test_on_login_refreshes_menu_state_after_dialog_closes():
    menu = _import_menu()

    with patch("anki_concursos.gui.menu.mw") as mock_mw, \
         patch("anki_concursos.gui.menu.LoginDialog") as login_dialog, \
         patch("anki_concursos.gui.menu.refresh_menu_state") as refresh:
        menu.on_login()

        login_dialog.assert_called_once_with(mock_mw.anki_concursos_api, mock_mw)
        login_dialog.return_value.exec.assert_called_once()
        refresh.assert_called_once()
