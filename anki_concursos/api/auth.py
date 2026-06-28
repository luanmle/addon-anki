import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

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

    def _read_data(self) -> Dict[str, Any]:
        if not self.token_file.exists():
            return {}
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"Failed to read auth data: {e}")
            return {}

    def _write_data(self, data: Dict[str, Any]) -> None:
        tmp_file = self.token_file.with_name(f"{self.token_file.name}.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        tmp_file.replace(self.token_file)

    def save_token(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        try:
            data = self._read_data()
            data["access_token"] = access_token
            if refresh_token:
                data["refresh_token"] = refresh_token
            else:
                data.pop("refresh_token", None)
            if email:
                data["email"] = email
            self._write_data(data)
        except Exception as e:
            logger.error(f"Failed to save token: {e}")

    def get_token(self) -> Optional[str]:
        token = self._read_data().get("access_token")
        return token if isinstance(token, str) else None

    def get_refresh_token(self) -> Optional[str]:
        refresh_token = self._read_data().get("refresh_token")
        return refresh_token if isinstance(refresh_token, str) else None

    def get_email(self) -> Optional[str]:
        email = self._read_data().get("email")
        return email if isinstance(email, str) else None

    def clear_token(self) -> None:
        try:
            if self.token_file.exists():
                self.token_file.unlink()
        except Exception as e:
            logger.error(f"Failed to clear token: {e}")
