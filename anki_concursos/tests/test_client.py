import pytest
import json
import urllib.error
from unittest.mock import patch, MagicMock

from anki_concursos.api.client import ApiClient, ApiError
from anki_concursos.api.models import TokenResponse, AnkiDeckSyncResponse, AnkiSyncChangeResponse

def make_mock_response(status_code=200, body_dict=None):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body_dict or {}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp

def make_http_error(status_code, body_dict=None):
    fp = MagicMock()
    fp.read.return_value = json.dumps(body_dict or {}).encode("utf-8")
    err = urllib.error.HTTPError("http://test", status_code, "HTTP Error", {}, fp)
    return err

@pytest.fixture
def mock_auth():
    with patch("anki_concursos.api.client.AuthService") as mock_class:
        instance = mock_class.return_value
        tokens = {"access_token": "valid_token", "refresh_token": "valid_refresh"}
        
        instance.get_token.side_effect = lambda: tokens.get("access_token")
        instance.get_refresh_token.side_effect = lambda: tokens.get("refresh_token")
        
        def save_token(access, refresh=None):
            tokens["access_token"] = access
            if refresh:
                tokens["refresh_token"] = refresh
        instance.save_token.side_effect = save_token
        
        def clear_token():
            tokens.clear()
        instance.clear_token.side_effect = clear_token
        
        yield instance, tokens

def test_api_error_parsing():
    # Test message and code parsing from JSON error body
    body = {"detail": "Chave expirada", "code": "token_expired"}
    err = ApiError("Default Msg", status_code=400, response_body=json.dumps(body))
    assert err.code == "token_expired"
    assert str(err) == "Chave expirada"

def test_request_success(mock_auth):
    client = ApiClient()
    mock_data = {"key": "value"}
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict=mock_data)
        
        res = client._request("GET", "/test-endpoint", require_auth=True)
        assert res == mock_data
        
        # Verify request parameters
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        assert req.full_url == f"{client.base_url}/test-endpoint"
        assert req.headers.get("Authorization") == "Bearer valid_token"

def test_login_saves_tokens(mock_auth):
    auth_instance, tokens = mock_auth
    client = ApiClient()
    
    login_response = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "user_id": "u1",
            "email": "test@test.com",
            "display_name": "Luan",
            "role": "student"
        }
    }
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict=login_response)
        
        res = client.login("test@test.com", "password")
        
        assert isinstance(res, TokenResponse)
        assert res.access_token == "new_access"
        assert res.refresh_token == "new_refresh"
        assert tokens["access_token"] == "new_access"
        assert tokens["refresh_token"] == "new_refresh"

def test_request_token_refresh_on_401(mock_auth):
    auth_instance, tokens = mock_auth
    client = ApiClient()
    
    # Simulates first request failing with 401,
    # refresh succeeding with new tokens,
    # and second retry request succeeding.
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            make_http_error(401, {"detail": "Token expired", "code": "token_expired"}),  # First request fails
            make_mock_response(body_dict={"access_token": "fresh_access", "refresh_token": "fresh_refresh"}),  # Refresh call succeeds
            make_mock_response(body_dict={"data": "success"})  # Retry call succeeds
        ]
        
        res = client._request("GET", "/secure-data", require_auth=True)
        assert res == {"data": "success"}
        assert tokens["access_token"] == "fresh_access"
        assert tokens["refresh_token"] == "fresh_refresh"
        assert mock_urlopen.call_count == 3

def test_request_token_refresh_failure(mock_auth):
    auth_instance, tokens = mock_auth
    client = ApiClient()
    
    # First request fails with 401, refresh call fails with 401
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            make_http_error(401, {"detail": "Token expired", "code": "token_expired"}),
            make_http_error(401, {"detail": "Refresh token expired", "code": "refresh_expired"})
        ]
        
        with pytest.raises(ApiError) as exc_info:
            client._request("GET", "/secure-data", require_auth=True)
            
        assert exc_info.value.status_code == 401
        assert "access_token" not in tokens  # verify token was cleared
        assert mock_urlopen.call_count == 2

def test_sync_deck_passes_pagination(mock_auth):
    client = ApiClient()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict={
            "deck_id": "d1",
            "from_release": 0,
            "to_release": 2,
            "has_changes": True,
            "changes": []
        })
        
        client.sync_deck("d1", since_release=0, page=2, page_size=100)
        
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        assert "page=2" in req.full_url
        assert "page_size=100" in req.full_url

def test_sync_deck_all_pages_concatenation(mock_auth):
    client = ApiClient()
    
    page_1 = {
        "deck_id": "d1", "from_release": 0, "to_release": 2, "has_changes": True,
        "page": 1, "pages": 2, "total_changes": 2,
        "changes": [
            {"release_id": "r1", "release_number": 1, "published_at": "2026", "action": "added", "card_id": "c1", "public_id": "P1", "old_card_version_id": None, "new_card_version_id": "v1", "tags": []}
        ]
    }
    page_2 = {
        "deck_id": "d1", "from_release": 0, "to_release": 2, "has_changes": True,
        "page": 2, "pages": 2, "total_changes": 2,
        "changes": [
            {"release_id": "r2", "release_number": 2, "published_at": "2026", "action": "added", "card_id": "c2", "public_id": "P2", "old_card_version_id": None, "new_card_version_id": "v1", "tags": []}
        ]
    }
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            make_mock_response(body_dict=page_1),
            make_mock_response(body_dict=page_2)
        ]
        
        res = client.sync_deck_all_pages("d1", since_release=0, page_size=1)
        assert len(res.changes) == 2
        assert res.changes[0].card_id == "c1"
        assert res.changes[1].card_id == "c2"
        assert mock_urlopen.call_count == 2

def test_get_addon_status(mock_auth):
    client = ApiClient()
    status_response = {
        "api_version": "1",
        "min_addon_version": "0.1.0",
        "supported_note_types": ["basic", "cloze"]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict=status_response)
        res = client.get_addon_status()
        assert res == status_response

def test_api_client_url_resolution():
    with patch("anki_concursos.api.client.mw") as mock_mw:
        # Scenario 1: Only api_environment is set to local
        mock_mw.addonManager.getConfig.return_value = {"api_environment": "local"}
        client = ApiClient()
        assert client.base_url == "http://localhost:8000"
        
        # Scenario 2: api_url is set and overrides environment
        mock_mw.addonManager.getConfig.return_value = {
            "api_environment": "staging",
            "api_url": "https://custom-domain.com"
        }
        client = ApiClient()
        assert client.base_url == "https://custom-domain.com"
        
        # Scenario 3: Neither set, falls back to default staging URL
        mock_mw.addonManager.getConfig.return_value = {}
        client = ApiClient()
        assert client.base_url == "https://flashcards-stagging-d9c092f5d04d.herokuapp.com"
        
        # Scenario 4: api_environment set to production, api_url empty
        mock_mw.addonManager.getConfig.return_value = {
            "api_environment": "production",
            "api_url": ""
        }
        client = ApiClient()
        assert client.base_url == "https://api.ankiconcursos.com.br"


def test_request_token_401_no_refresh_token(mock_auth):
    auth_instance, tokens = mock_auth
    client = ApiClient()
    # Remove refresh token so we can't refresh
    tokens.pop("refresh_token", None)
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = make_http_error(401, {"detail": "Token expired", "code": "token_expired"})
        
        with pytest.raises(ApiError) as exc_info:
            client._request("GET", "/secure-data", require_auth=True)
            
        assert exc_info.value.status_code == 401
        assert "access_token" not in tokens  # verify token was cleared
        assert mock_urlopen.call_count == 1


def test_sync_deck_all_pages_no_pages_field(mock_auth):
    client = ApiClient()
    # Response has pages=None
    response_body = {
        "deck_id": "d1", "from_release": 0, "to_release": 5, "has_changes": True,
        "page": None, "pages": None, "total_changes": 1,
        "changes": [
            {"release_id": "r1", "release_number": 1, "published_at": "2026", "action": "added", "card_id": "c1", "public_id": "P1", "old_card_version_id": None, "new_card_version_id": "v1", "tags": []}
        ]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict=response_body)
        
        res = client.sync_deck_all_pages("d1", since_release=0, page_size=100)
        assert len(res.changes) == 1
        assert res.changes[0].card_id == "c1"
        assert mock_urlopen.call_count == 1  # only one request should be made


def test_get_addon_status_404(mock_auth):
    client = ApiClient()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = make_http_error(404, {"detail": "Not Found"})
        res = client.get_addon_status()
        assert res == {}  # Should return empty dict on 404 instead of raising ApiError


def test_parse_dataclass_filters_extra_keys():
    from anki_concursos.api.client import parse_dataclass
    from anki_concursos.api.models import UserResponse
    
    # Simulates JSON response from server containing undocumented 'is_active' and 'created_at' fields
    payload = {
        "user_id": "u1",
        "email": "test@test.com",
        "display_name": "Luan",
        "role": "student",
        "is_active": True,
        "created_at": "2026-06-16T22:00:00"
    }
    
    # It should not fail with TypeError: got an unexpected keyword argument
    user = parse_dataclass(UserResponse, payload)
    assert isinstance(user, UserResponse)
    assert user.user_id == "u1"
    assert user.email == "test@test.com"
    assert user.display_name == "Luan"
    assert user.role == "student"
    assert not hasattr(user, "is_active")
    assert not hasattr(user, "created_at")


def test_upload_deck_success(mock_auth):
    client = ApiClient()
    mock_resp_body = {
        "deck_id": "d1-uuid",
        "deck_name": "Test Deck",
        "snapshot_id": "snap-uuid",
        "published": True,
        "total_notes": 1,
        "created_cards": 1,
        "reused_cards": 0,
        "items": []
    }
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict=mock_resp_body)
        
        payload = {
            "deck_name": "Test Deck",
            "description": "A deck",
            "source_name": "addon",
            "publish_release": True,
            "templates": [],
            "notes": []
        }
        
        res = client.upload_deck(payload)

        assert res == mock_resp_body
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        assert req.method == "POST"
        assert "/addon/decks/upload" in req.full_url
        assert req.headers.get("Authorization") == "Bearer valid_token"


def test_upload_deck_batches_large_payload(mock_auth):
    """Decks exceeding BATCH_SIZE notes are split into multiple POSTs."""
    client = ApiClient()
    mock_resp_body = {
        "deck_id": "d1", "deck_name": "Big Deck", "snapshot_id": "s1",
        "published": True, "total_notes": 1, "created_cards": 1, "reused_cards": 0, "items": [],
    }

    note = {"note_type": "Basic", "card_kind": "basic", "fields": {"Front": "Q"}, "tags": []}
    templates = [{"template_name": "Card 1", "note_type": "Basic", "card_kind": "basic",
                  "fields": ["Front"], "field_mapping": {}, "front_html": "{{Front}}", "back_html": "{{Back}}", "styling_css": ""}]
    total_notes = client._UPLOAD_BATCH_SIZE + 10  # one batch over the limit
    payload = {
        "deck_name": "Big Deck", "source_name": "addon", "publish_release": True,
        "templates": templates, "notes": [note] * total_notes,
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = make_mock_response(body_dict=mock_resp_body)
        client.upload_deck(payload)

    assert mock_urlopen.call_count == 2  # two batches

    # First batch must NOT publish
    first_body = json.loads(mock_urlopen.call_args_list[0][0][0].data)
    assert first_body["publish_release"] is False
    assert len(first_body["notes"]) == client._UPLOAD_BATCH_SIZE
    assert first_body["templates"] == templates

    # Last batch must publish and contain remaining notes
    last_body = json.loads(mock_urlopen.call_args_list[1][0][0].data)
    assert last_body["publish_release"] is True
    assert len(last_body["notes"]) == 10


def test_upload_deck_retries_on_connection_aborted(mock_auth):
    """ConnectionAbortedError (WinError 10053) triggers one retry."""
    client = ApiClient()
    mock_resp_body = {"deck_id": "d1", "deck_name": "D", "snapshot_id": "s1",
                      "published": True, "total_notes": 1, "created_cards": 1, "reused_cards": 0, "items": []}

    aborted = urllib.error.URLError(ConnectionAbortedError(10053, "aborted"))

    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("time.sleep"):
        mock_urlopen.side_effect = [aborted, make_mock_response(body_dict=mock_resp_body)]
        payload = {"deck_name": "D", "source_name": "addon", "publish_release": True,
                   "templates": [{"template_name": "T", "note_type": "Basic", "card_kind": "basic",
                                   "fields": ["F"], "field_mapping": {}, "front_html": "{{F}}", "back_html": "", "styling_css": ""}],
                   "notes": [{"note_type": "Basic", "card_kind": "basic", "fields": {"F": "v"}, "tags": []}]}
        res = client.upload_deck(payload)

    assert mock_urlopen.call_count == 2
    assert res["deck_id"] == "d1"

