from aqt import mw
from ..api.client import ApiClient
from ..storage.database import DatabaseManager
from ..sync.engine import SyncEngine

def on_profile_did_open() -> None:
    """Triggered when Anki profile loads. Auto-sync if configured."""
    if not mw or not mw.addonManager:
        return
        
    try:
        addon_folder = __name__.split('.')[0]
        config = mw.addonManager.getConfig(addon_folder) or {}
        
        if config.get("auto_sync", False):
            if not hasattr(mw, "anki_concursos_api"):
                mw.anki_concursos_db = DatabaseManager()
                mw.anki_concursos_api = ApiClient()
                
            engine = SyncEngine(mw.anki_concursos_api, mw.anki_concursos_db)
            
            def silent_callback(success: bool, msg: str) -> None:
                if not success:
                    print(f"Anki Concursos Auto-Sync Failed: {msg}")
                    
            engine.sync_all(silent_callback)
    except Exception:
        pass
