import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional

from aqt import mw

from .auth import AuthService
from .models import (
    UserResponse, TokenResponse, SubscribableDeckResponse, 
    SubscribableDeckListResponse, DeckSubscriptionResponse, 
    DeckSubscriptionListResponse, AnkiDeckManifestResponse, 
    AnkiSyncChangeResponse, AnkiDeckSyncResponse
)
from ..consts import DEFAULT_API_URL, VERSION

logger = logging.getLogger("anki_concursos.api.client")

class ApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

class ApiClient:
    def __init__(self):
        self.auth_service = AuthService()
        self.base_url = DEFAULT_API_URL
        if mw and mw.addonManager:
            # We must use __name__.split('.')[0] to get the top level package name 
            # if we are deeply nested. Or __name__ if we use relative imports.
            try:
                # Get the addon folder name
                addon_folder = __name__.split('.')[0]
                config = mw.addonManager.getConfig(addon_folder) or {}
                self.base_url = config.get("api_url", DEFAULT_API_URL).rstrip("/")
            except Exception:
                pass
        self.timeout = 30
        
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, require_auth: bool = True) -> Any:
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Accept": "application/json",
            "User-Agent": f"AnkiConcursos/{VERSION}"
        }
        
        if data is not None:
            headers["Content-Type"] = "application/json"
            encoded_data = json.dumps(data).encode("utf-8")
        else:
            encoded_data = None
            
        if require_auth:
            token = self.auth_service.get_token()
            if not token:
                raise ApiError("Not authenticated", status_code=401)
            headers["Authorization"] = f"Bearer {token}"
            
        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return None
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            logger.error(f"HTTPError {e.code} on {method} {url}: {body}")
            raise ApiError(f"HTTP Error {e.code}", status_code=e.code, response_body=body)
        except urllib.error.URLError as e:
            logger.error(f"URLError on {method} {url}: {e.reason}")
            raise ApiError(f"Connection Error: {e.reason}")
            
    def login(self, email: str, password: str) -> TokenResponse:
        """Login and save token. Does not return TokenResponse directly since auth_service handles it, but we can return it."""
        # Using URL encoding for form data since FastAPI OAuth2PasswordRequestForm expects form data, 
        # but the backend docs say POST /auth/token or similar. Actually, the schema uses LoginRequest which is JSON!
        # Wait, the auth schema has LoginRequest with email and password fields. We will send JSON.
        data = {"email": email, "password": password}
        resp = self._request("POST", "/auth/token", data=data, require_auth=False)
        self.auth_service.save_token(resp["access_token"])
        return TokenResponse(
            access_token=resp["access_token"],
            token_type=resp["token_type"],
            expires_in=resp["expires_in"],
            user=UserResponse(**resp["user"])
        )
        
    def get_current_user(self) -> UserResponse:
        resp = self._request("GET", "/auth/me")
        return UserResponse(**resp)
        
    def list_subscribable_decks(self, page: int = 1, page_size: int = 50) -> SubscribableDeckListResponse:
        resp = self._request("GET", f"/subscriptions/decks?page={page}&page_size={page_size}")
        items = [SubscribableDeckResponse(**item) for item in resp.get("items", [])]
        return SubscribableDeckListResponse(
            items=items,
            page=resp["page"],
            page_size=resp["page_size"],
            total=resp["total"],
            pages=resp["pages"]
        )
        
    def list_subscriptions(self) -> DeckSubscriptionListResponse:
        resp = self._request("GET", "/subscriptions")
        items = [DeckSubscriptionResponse(**item) for item in resp.get("items", [])]
        return DeckSubscriptionListResponse(items=items, total=resp["total"])
        
    def subscribe(self, deck_id: str) -> DeckSubscriptionResponse:
        resp = self._request("POST", f"/subscriptions/{deck_id}")
        return DeckSubscriptionResponse(**resp)
        
    def unsubscribe(self, deck_id: str) -> DeckSubscriptionResponse:
        resp = self._request("POST", f"/subscriptions/{deck_id}/cancel")
        return DeckSubscriptionResponse(**resp)
        
    def get_deck_manifest(self, deck_id: str) -> AnkiDeckManifestResponse:
        resp = self._request("GET", f"/addon/decks/{deck_id}/manifest")
        return AnkiDeckManifestResponse(**resp)
        
    def sync_deck(self, deck_id: str, since_release: int) -> AnkiDeckSyncResponse:
        resp = self._request("GET", f"/addon/decks/{deck_id}/sync?since_release={since_release}")
        changes = [AnkiSyncChangeResponse(**c) for c in resp.get("changes", [])]
        return AnkiDeckSyncResponse(
            deck_id=resp["deck_id"],
            from_release=resp["from_release"],
            to_release=resp["to_release"],
            has_changes=resp["has_changes"],
            changes=changes
        )
