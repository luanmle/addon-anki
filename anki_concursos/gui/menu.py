from aqt import mw
from aqt.qt import *
from aqt.operations import QueryOp

from .login_dialog import LoginDialog
# from .settings_dialog import SettingsDialog
# from .deck_browser import DeckBrowser
# from .status_dialog import StatusDialog
from ..api.client import ApiClient
from ..storage.database import DatabaseManager
from ..sync.engine import SyncEngine

def setup_menu() -> None:
    if not mw:
        return
        
    menu = QMenu("Anki Concursos", mw)
    mw.form.menubar.insertMenu(mw.form.menuTools.menuAction(), menu)
    
    # Store instances so they don't get garbage collected immediately
    mw.anki_concursos_db = DatabaseManager()
    mw.anki_concursos_api = ApiClient()
    menu.aboutToShow.connect(refresh_menu_state)
    
    a_sync = QAction("Sincronizar agora", mw)
    a_sync.setShortcut("Ctrl+Shift+C")
    a_sync.triggered.connect(on_sync)
    menu.addAction(a_sync)

    a_check_db = QAction("Verificar banco local", mw)
    a_check_db.triggered.connect(on_check_local_database)
    menu.addAction(a_check_db)
    
    a_decks = QAction("Explorar baralhos", mw)
    a_decks.triggered.connect(on_browse_decks)
    menu.addAction(a_decks)
    
    a_status = QAction("Minhas inscrições", mw)
    a_status.triggered.connect(on_status)
    menu.addAction(a_status)
    
    a_upload = QAction("Enviar baralho", mw)
    a_upload.triggered.connect(on_upload_deck)
    menu.addAction(a_upload)
    
    menu.addSeparator()
    
    a_login = QAction("Entrar / Sair", mw)
    a_login.triggered.connect(on_login)
    menu.addAction(a_login)
    mw.anki_concursos_login_action = a_login
    
    a_settings = QAction("Configurações", mw)
    a_settings.triggered.connect(on_settings)
    menu.addAction(a_settings)
    refresh_menu_state()

def on_sync() -> None:
    if not _ensure_authenticated():
        return
    engine = SyncEngine(mw.anki_concursos_api, mw.anki_concursos_db)
    
    def callback(success: bool, message: str) -> None:
        if success:
            QMessageBox.information(mw, "Sincronização concluída", message)
        else:
            QMessageBox.critical(mw, "Falha na sincronização", message)
            
    engine.sync_all(callback)

def on_check_local_database() -> None:
    def on_success(repaired_rows: int) -> None:
        if repaired_rows:
            suffix = "linha" if repaired_rows == 1 else "linhas"
            QMessageBox.information(
                mw,
                "Verificação do banco local",
                f"🧰 Reparadas {repaired_rows} {suffix} de metadados locais de sync.",
            )
        else:
            QMessageBox.information(
                mw,
                "Verificação do banco local",
                "Banco local de sync OK. Nenhum reparo necessário.",
            )

    def on_failure(exc: Exception) -> None:
        QMessageBox.critical(
            mw,
            "Falha na verificação do banco local",
            str(exc),
        )

    op = QueryOp(
        parent=mw,
        op=lambda _: mw.anki_concursos_db.repair_integrity(),
        success=on_success,
    )
    op.failure(on_failure)
    op.with_progress("Verificando banco local...").run_in_background()

def on_browse_decks() -> None:
    if not _ensure_authenticated():
        return
    from .deck_browser import DeckBrowser
    dlg = DeckBrowser(mw.anki_concursos_api, mw.anki_concursos_db, mw)
    dlg.exec()

def on_status() -> None:
    if not _ensure_authenticated():
        return
    from .status_dialog import StatusDialog
    dlg = StatusDialog(mw.anki_concursos_api, mw.anki_concursos_db, mw)
    dlg.exec()

def on_upload_deck() -> None:
    if not _ensure_authenticated():
        return
    from .upload_dialog import UploadDialog
    dlg = UploadDialog(mw.anki_concursos_api, mw)
    dlg.exec()

def on_login() -> None:
    dlg = LoginDialog(mw.anki_concursos_api, mw)
    dlg.exec()
    refresh_menu_state()

def on_settings() -> None:
    from .settings_dialog import SettingsDialog
    dlg = SettingsDialog(mw.anki_concursos_api, mw)
    dlg.exec()

def _ensure_authenticated() -> bool:
    if mw.anki_concursos_api.auth_service.get_token():
        return True

    dlg = LoginDialog(mw.anki_concursos_api, mw)
    dlg.exec()
    refresh_menu_state()
    if mw.anki_concursos_api.auth_service.get_token():
        return True

    QMessageBox.warning(
        mw,
        "Login necessário",
        "Faça login para usar esta ação.",
    )
    return False

def refresh_menu_state() -> None:
    action = getattr(mw, "anki_concursos_login_action", None)
    if not action:
        return

    auth = mw.anki_concursos_api.auth_service
    if auth.get_token():
        email = auth.get_email()
        action.setText(f"Login ativo: {email}" if email else "Login ativo")
    else:
        action.setText("Entrar")
