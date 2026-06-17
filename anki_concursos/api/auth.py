import json
import logging
from pathlib import Path
from typing import Optional

from aqt import mw

logger = logging.getLogger("anki_concursos.api.auth")

class AuthService:
    def __init__(self):
        if mw and mw.addonManager:
            addon_dir = Path(__file__).parent.parent
            self.token_file = addon_dir / "user_files" / "auth.json"
        else:
            self.token_file = Path("auth.json")
            
        self.token_file.parent.mkdir(exist_ok=True, parents=True)

    def save_token(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        try:
            data = {"access_token": access_token}
            if refresh_token:
                data["refresh_token"] = refresh_token
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save token: {e}")

    def get_token(self) -> Optional[str]:
        if not self.token_file.exists():
            return None
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("access_token")
        except Exception as e:
            logger.error(f"Failed to read token: {e}")
            return None

    def get_refresh_token(self) -> Optional[str]:
        if not self.token_file.exists():
            return None
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("refresh_token")
        except Exception as e:
            logger.error(f"Failed to read refresh token: {e}")
            return None


    def clear_token(self) -> None:
        try:
            if self.token_file.exists():
                self.token_file.unlink()
        except Exception as e:
            logger.error(f"Failed to clear token: {e}")
