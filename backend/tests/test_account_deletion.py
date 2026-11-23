"""
Self-service account deletion (KVKK / GDPR erasure).

The database side (cascade to every user table, other users untouched, contributed books kept
without the link to the person) is tested in backend/tests/sql/test_16_account_deletion.sql.
Here: the API contract and that the RPC runs with the reader's own JWT, never a service key.
"""

from unittest.mock import MagicMock, patch

import pytest
from backend.app import create_app
from backend.application.use_cases.account import DeleteAccountUseCase
from backend.domain.ports import AccountDeletionUnavailable
from backend.infrastructure.persistence.supabase_adapters import SupabaseAccountAdapter

pytestmark = pytest.mark.unit


class FakeAccountPort:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    def delete_current_account(self, user_token):
        if self.error:
            raise self.error
        self.calls.append(user_token)


def test_use_case_requires_explicit_confirmation():
    port = FakeAccountPort()
    uc = DeleteAccountUseCase(port)
    for confirm in (None, False, "true", 1):
        with pytest.raises(ValueError):
            uc.execute("u1", "jwt", confirm)
    assert port.calls == []
    uc.execute("u1", "jwt", True)
    assert port.calls == ["jwt"]


def test_use_case_requires_an_authenticated_user():
    with pytest.raises(PermissionError):
        DeleteAccountUseCase(FakeAccountPort()).execute("", "jwt", True)
    with pytest.raises(PermissionError):
        DeleteAccountUseCase(FakeAccountPort()).execute("u1", None, True)


@pytest.fixture
def client(monkeypatch):
    from backend.routes import routes

    port = FakeAccountPort()
    monkeypatch.setattr(routes.container, "delete_account_uc", DeleteAccountUseCase(port), raising=False)
    app = create_app()
    app.config["TESTING"] = True

    @app.before_request
    def fake_auth():  # stands in for the JWT check, which TESTING skips
        from flask import g
        g.user_id, g.jwt_token = "user-1", "the-users-own-jwt"

    return app.test_client(), port, monkeypatch, routes


def test_delete_account_endpoint(client):
    c, port, _, _ = client
    assert c.delete("/api/account", json={}).status_code == 400
    assert c.delete("/api/account", json={"confirm": "yes"}).status_code == 400
    assert port.calls == []
    res = c.delete("/api/account", json={"confirm": True})
    assert res.status_code == 200 and res.get_json() == {"status": "deleted"}
    assert port.calls == ["the-users-own-jwt"]  # the token from the verified request, not from the body


def test_delete_account_unavailable_is_an_honest_503(client):
    c, _, monkeypatch, routes = client
    monkeypatch.setattr(routes.container, "delete_account_uc",
                        DeleteAccountUseCase(FakeAccountPort(AccountDeletionUnavailable("rpc missing"))), raising=False)
    assert c.delete("/api/account", json={"confirm": True}).status_code == 503
    monkeypatch.setattr(routes.container, "delete_account_uc", None, raising=False)
    assert c.delete("/api/account", json={"confirm": True}).status_code == 503


def test_unauthenticated_request_is_rejected():
    app = create_app()
    app.config["TESTING"] = True
    app.config["ENFORCE_AUTH_IN_TESTS"] = True
    assert app.test_client().delete("/api/account", json={"confirm": True}).status_code == 401


def test_adapter_calls_the_rpc_with_the_users_jwt():
    fake = MagicMock()
    with patch("supabase.create_client", return_value=fake) as create:
        SupabaseAccountAdapter().delete_current_account("user-jwt")
    create.assert_called_once()
    assert "service" not in str(create.call_args).lower()
    fake.postgrest.auth.assert_called_once_with("user-jwt")
    fake.rpc.assert_called_once_with("delete_my_account", {})


def test_adapter_reports_a_missing_rpc_as_unavailable():
    fake = MagicMock()
    fake.rpc.return_value.execute.side_effect = RuntimeError("PGRST202 Could not find the function delete_my_account")
    with patch("supabase.create_client", return_value=fake), pytest.raises(AccountDeletionUnavailable):
        SupabaseAccountAdapter().delete_current_account("user-jwt")
