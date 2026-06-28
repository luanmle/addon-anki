import json

from anki_concursos.api.auth import AuthService


def make_auth_service(tmp_path):
    service = AuthService()
    service.token_file = tmp_path / "auth.json"
    return service


def test_auth_service_saves_login_email(tmp_path):
    service = make_auth_service(tmp_path)

    service.save_token("access", "refresh", email="user@example.com")

    assert service.get_token() == "access"
    assert service.get_refresh_token() == "refresh"
    assert service.get_email() == "user@example.com"


def test_auth_service_preserves_email_when_token_refreshes(tmp_path):
    service = make_auth_service(tmp_path)
    service.save_token("access", "refresh", email="user@example.com")

    service.save_token("new-access", "new-refresh")

    assert service.get_token() == "new-access"
    assert service.get_refresh_token() == "new-refresh"
    assert service.get_email() == "user@example.com"


def test_auth_service_clear_token_removes_session(tmp_path):
    service = make_auth_service(tmp_path)
    service.save_token("access", "refresh", email="user@example.com")

    service.clear_token()

    assert service.get_token() is None
    assert service.get_refresh_token() is None
    assert service.get_email() is None
    assert not service.token_file.exists()


def test_auth_service_ignores_invalid_json(tmp_path):
    service = make_auth_service(tmp_path)
    service.token_file.write_text("{invalid", encoding="utf-8")

    assert service.get_token() is None
    assert service.get_refresh_token() is None
    assert service.get_email() is None


def test_auth_service_writes_json_atomically(tmp_path):
    service = make_auth_service(tmp_path)

    service.save_token("access", email="user@example.com")

    data = json.loads(service.token_file.read_text(encoding="utf-8"))
    assert data == {
        "access_token": "access",
        "email": "user@example.com",
    }
