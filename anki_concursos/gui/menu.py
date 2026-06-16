from aqt import mw
from aqt.qt import *

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
    
    a_sync = QAction("Sync Now", mw)
    a_sync.setShortcut("Ctrl+Shift+C")
    a_sync.triggered.connect(on_sync)
    menu.addAction(a_sync)
    
    a_decks = QAction("Browse Decks", mw)
    a_decks.triggered.connect(on_browse_decks)
    menu.addAction(a_decks)
    
    a_status = QAction("My Subscriptions", mw)
    a_status.triggered.connect(on_status)
    menu.addAction(a_status)
    
    menu.addSeparator()
    
    a_login = QAction("Login / Logout", mw)
    a_login.triggered.connect(on_login)
    menu.addAction(a_login)
    
    a_settings = QAction("Settings", mw)
    a_settings.triggered.connect(on_settings)
    menu.addAction(a_settings)

def on_sync() -> None:
    engine = SyncEngine(mw.anki_concursos_api, mw.anki_concursos_db)
    
    def callback(success: bool, message: str) -> None:
        if success:
            QMessageBox.information(mw, "Sync Complete", message)
        else:
            QMessageBox.critical(mw, "Sync Failed", message)
            
    engine.sync_all(callback)

def on_browse_decks() -> None:
    from .deck_browser import DeckBrowser
    dlg = DeckBrowser(mw.anki_concursos_api, mw.anki_concursos_db, mw)
    dlg.exec()

def on_status() -> None:
    from .status_dialog import StatusDialog
    dlg = StatusDialog(mw.anki_concursos_db, mw)
    dlg.exec()

def on_login() -> None:
    dlg = LoginDialog(mw.anki_concursos_api, mw)
    dlg.exec()

def on_settings() -> None:
    from .settings_dialog import SettingsDialog
    dlg = SettingsDialog(mw.anki_concursos_api, mw)
    dlg.exec()
