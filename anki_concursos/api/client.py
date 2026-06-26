import json
import logging
import urllib.request
import urllib.error
import urllib.parse
import dataclasses
from typing import Dict, Any, Optional

from aqt import mw

from .auth import AuthService
from .models import (
    UserResponse, TokenResponse, SubscribableDeckResponse,
    SubscribableDeckListResponse, DeckSubscriptionResponse,
    DeckSubscriptionListResponse, AnkiDeckManifestResponse,
    AnkiSyncChangeResponse, AnkiDeckSyncResponse, AnkiDeckTemplateResponse,
    AnkiDeckStateResponse, AnkiDeckStateCardResponse
)
from ..consts import DEFAULT_API_URL, API_ENVIRONMENTS, DEFAULT_API_ENVIRONMENT, VERSION

logger = logging.getLogger("anki_concursos.api.client")

class ApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.status_code = status_code
        self.response_body = response_body
        self.code = None
        
        if response_body:
            try:
                data = json.loads(response_body)
                if isinstance(data, dict):
                    self.code = data.get("code")
                    if "detail" in data:
                        message = data["detail"]
            except Exception:
                pass
                
        # Translate common error patterns to Portuguese for user display
        lower_msg = message.lower()
        if "not subscribed" in lower_msg or "sem assinatura" in lower_msg or self.code == "not_subscribed":
            message = "Você não possui uma assinatura ativa para este baralho."
        elif "not published" in lower_msg or "não publicado" in lower_msg or self.code == "deck_not_published":
            message = "Este baralho ainda não foi publicado na plataforma."
        elif "token expired" in lower_msg or "token_expired" in lower_msg:
            message = "Sessão expirada. Por favor, faça login novamente."
        elif "unauthorized" in lower_msg or "incorrect email or password" in lower_msg or "invalid credentials" in lower_msg:
            message = "Email ou senha incorretos."
        elif "connection" in lower_msg or "getaddrinfo" in lower_msg or "timed out" in lower_msg:
            message = "Não foi possível conectar ao servidor. Verifique sua conexão com a internet ou a URL da API."
            
        super().__init__(message)


def parse_dataclass(cls, data: dict):
    if not isinstance(data, dict):
        return data
    class_fields = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in class_fields}
    return cls(**filtered)


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
                environment = config.get("api_environment", DEFAULT_API_ENVIRONMENT)
                configured_url = config.get("api_url", "").strip()
                
                if configured_url:
                    self.base_url = configured_url.rstrip("/")
                else:
                    self.base_url = API_ENVIRONMENTS.get(environment, DEFAULT_API_URL).rstrip("/")
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
                raise ApiError("Usuário não autenticado. Por favor, realize o login para sincronizar.", status_code=401)
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
            if e.code == 401:
                if require_auth:
                    logger.info("Access token expired (401). Attempting token refresh...")
                    new_token = None
                    try:
                        new_token = self.refresh_token()
                    except Exception as refresh_err:
                        logger.warning(f"Refresh token endpoint failed or not supported by backend: {refresh_err}")
                        
                    if new_token:
                        headers["Authorization"] = f"Bearer {new_token}"
                        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
                        try:
                            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                                body = response.read().decode("utf-8")
                                if not body:
                                    return None
                                return json.loads(body)
                        except urllib.error.HTTPError as retry_e:
                            body = retry_e.read().decode("utf-8") if retry_e.fp else ""
                            logger.error(f"HTTPError {retry_e.code} on retry of {method} {url}: {body}")
                            if retry_e.code == 401:
                                self.auth_service.clear_token()
                                raise ApiError("Sessão expirada. Por favor, faça login novamente.", status_code=401, response_body=body)
                            raise ApiError(f"HTTP Error {retry_e.code}", status_code=retry_e.code, response_body=body)
                    else:
                        self.auth_service.clear_token()
                        raise ApiError("Sessão expirada. Por favor, faça login novamente.", status_code=401, response_body=body)
                else:
                    self.auth_service.clear_token()
                    raise ApiError("Credenciais inválidas.", status_code=401, response_body=body)
                    
            logger.error(f"HTTPError {e.code} on {method} {url}: {body}")
            raise ApiError(f"HTTP Error {e.code}", status_code=e.code, response_body=body)
        except urllib.error.URLError as e:
            logger.error(f"URLError on {method} {url}: {e.reason}")
            raise ApiError(f"Não foi possível conectar ao servidor. Verifique sua conexão com a internet ou a URL da API: {e.reason}")
            
    def login(self, email: str, password: str) -> TokenResponse:
        """Login and save token. Does not return TokenResponse directly since auth_service handles it, but we can return it."""
        # Using URL encoding for form data since FastAPI OAuth2PasswordRequestForm expects form data, 
        # but the backend docs say POST /auth/token or similar. Actually, the schema uses LoginRequest which is JSON!
        # Wait, the auth schema has LoginRequest with email and password fields. We will send JSON.
        data = {"email": email, "password": password}
        resp = self._request("POST", "/auth/token", data=data, require_auth=False)
        self.auth_service.save_token(resp["access_token"], resp.get("refresh_token"))
        user_data = parse_dataclass(UserResponse, resp["user"]) if "user" in resp else None
        return TokenResponse(
            access_token=resp["access_token"],
            token_type=resp["token_type"],
            expires_in=resp["expires_in"],
            user=user_data,
            refresh_token=resp.get("refresh_token")
        )

    def refresh_token(self) -> Optional[str]:
        refresh_token = self.auth_service.get_refresh_token()
        if not refresh_token:
            return None
        try:
            resp = self._request("POST", "/auth/refresh", data={"refresh_token": refresh_token}, require_auth=False)
            new_access_token = resp["access_token"]
            new_refresh_token = resp.get("refresh_token")
            self.auth_service.save_token(new_access_token, new_refresh_token)
            return new_access_token
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            self.auth_service.clear_token()
            return None
        
    def get_current_user(self) -> UserResponse:
        resp = self._request("GET", "/auth/me")
        return parse_dataclass(UserResponse, resp)
        
    def list_subscribable_decks(self, page: int = 1, page_size: int = 50) -> SubscribableDeckListResponse:
        resp = self._request("GET", f"/subscriptions/decks?page={page}&page_size={page_size}")
        items = [parse_dataclass(SubscribableDeckResponse, item) for item in resp.get("items", [])]
        return SubscribableDeckListResponse(
            items=items,
            page=resp["page"],
            page_size=resp["page_size"],
            total=resp["total"],
            pages=resp["pages"]
        )
        
    def list_subscriptions(self) -> DeckSubscriptionListResponse:
        resp = self._request("GET", "/subscriptions")
        items = [parse_dataclass(DeckSubscriptionResponse, item) for item in resp.get("items", [])]
        return DeckSubscriptionListResponse(items=items, total=resp["total"])
        
    def subscribe(self, deck_id: str) -> DeckSubscriptionResponse:
        resp = self._request("POST", f"/subscriptions/{deck_id}")
        return parse_dataclass(DeckSubscriptionResponse, resp)
        
    def unsubscribe(self, deck_id: str) -> DeckSubscriptionResponse:
        resp = self._request("POST", f"/subscriptions/{deck_id}/cancel")
        return parse_dataclass(DeckSubscriptionResponse, resp)
        
    def get_deck_manifest(self, deck_id: str) -> AnkiDeckManifestResponse:
        resp = self._request("GET", f"/addon/decks/{deck_id}/manifest")
        templates = [parse_dataclass(AnkiDeckTemplateResponse, t) for t in resp.get("templates", [])]
        manifest = parse_dataclass(AnkiDeckManifestResponse, resp)
        manifest.templates = templates  # type: ignore[attr-defined]
        return manifest
        
    def sync_deck(self, deck_id: str, since_release: int, page: Optional[int] = None, page_size: Optional[int] = None, to_release: Optional[int] = None) -> AnkiDeckSyncResponse:
        url = f"/addon/decks/{deck_id}/sync?since_release={since_release}"
        if to_release is not None:
            url += f"&to_release={to_release}"
        if page is not None:
            url += f"&page={page}"
        if page_size is not None:
            url += f"&page_size={page_size}"

        resp = self._request("GET", url)
        changes = [parse_dataclass(AnkiSyncChangeResponse, c) for c in resp.get("changes", [])]
        return AnkiDeckSyncResponse(
            deck_id=resp["deck_id"],
            from_release=resp["from_release"],
            to_release=resp["to_release"],
            has_changes=resp["has_changes"],
            changes=changes,
            page=resp.get("page"),
            pages=resp.get("pages"),
            total_changes=resp.get("total_changes")
        )

    def sync_deck_all_pages(self, deck_id: str, since_release: int, page_size: int = 500) -> AnkiDeckSyncResponse:
        page = 1
        all_changes = []
        first_resp = self.sync_deck(deck_id, since_release, page=page, page_size=page_size)
        all_changes.extend(first_resp.changes)

        # Pin the release ceiling reported by page 1 so every later page reads
        # the same snapshot even if a new release is published mid-pagination.
        pinned_to_release = first_resp.to_release
        expected_total = first_resp.total_changes

        total_pages = first_resp.pages
        if total_pages is None or not isinstance(total_pages, int) or total_pages < 1:
            total_pages = 1

        # Avoid infinite loops by capping maximum pages
        max_pages = min(total_pages, 1000)
        while page < max_pages:
            page += 1
            next_resp = self.sync_deck(deck_id, since_release, page=page, page_size=page_size, to_release=pinned_to_release)
            if next_resp.to_release != pinned_to_release:
                raise ApiError(
                    "O baralho mudou durante a sincronização. Tente novamente."
                )
            all_changes.extend(next_resp.changes)

        # Completeness guard: the watermark must only advance once every change
        # up to `pinned_to_release` was fetched. Caller aborts (no watermark
        # advance) if this raises.
        if (
            isinstance(expected_total, int)
            and len(all_changes) != expected_total
        ):
            raise ApiError(
                f"Sincronização incompleta: {len(all_changes)}/{expected_total} "
                "mudanças recebidas. Tente novamente."
            )

        return AnkiDeckSyncResponse(
            deck_id=first_resp.deck_id,
            from_release=first_resp.from_release,
            to_release=pinned_to_release,
            has_changes=len(all_changes) > 0,
            changes=all_changes,
            total_changes=expected_total
        )
    def get_deck_state(self, deck_id: str) -> Optional[AnkiDeckStateResponse]:
        """Full active-card state at the latest release, for orphan reconcile.

        Returns None when the server does not expose the endpoint (404), so the
        client stays compatible with older backends (reconcile is skipped).
        """
        try:
            resp = self._request("GET", f"/addon/decks/{deck_id}/state")
        except ApiError as e:
            if e.status_code == 404:
                logger.info("Endpoint /state ausente (404); reconcile de deleções ignorado.")
                return None
            raise
        cards = [parse_dataclass(AnkiDeckStateCardResponse, c) for c in resp.get("cards", [])]
        return AnkiDeckStateResponse(
            deck_id=resp["deck_id"],
            latest_release=resp["latest_release"],
            total_active=resp.get("total_active", len(cards)),
            cards=cards,
        )

    def get_addon_status(self) -> Dict[str, Any]:
        """Fetch general status and minimum supported add-on version."""
        try:
            return self._request("GET", "/addon/status", require_auth=False)
        except ApiError as e:
            if e.status_code == 404:
                logger.info("O endpoint opcional /addon/status retornou 404 (Não Encontrado). Ignorando verificação de versão do add-on.")
            else:
                logger.warning(f"Failed to fetch addon status: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch addon status: {e}")
            return {}

    def upload_deck(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a complete deck to the platform."""
        return self._request("POST", "/addon/decks/upload", data=payload, require_auth=True)
