"""
CORS contract for the browser client (web/ on Vercel calls this API cross-origin).

There was no CORS test, so a flask-cors upgrade could change these headers unnoticed. Pinned:
allowed origins get credentials and the request headers the client sends; other origins get no
CORS grant; private-network access is not granted.
"""

import pytest
from backend.app import create_app
from backend.config import Config

pytestmark = pytest.mark.api

ALLOWED = "https://libris.example"
OTHER = "https://evil.example"


@pytest.fixture
def client():
    class Cfg(Config):
        ALLOWED_ORIGINS = [ALLOWED]

    app = create_app(Cfg)
    app.config["TESTING"] = True
    return app.test_client()


def test_allowed_origin_gets_credentials_and_vary(client):
    res = client.get("/api/health", headers={"Origin": ALLOWED})
    assert res.headers.get("Access-Control-Allow-Origin") == ALLOWED
    assert res.headers.get("Access-Control-Allow-Credentials") == "true"
    assert "Origin" in res.headers.get("Vary", "")


def test_other_origin_gets_no_cors_grant(client):
    res = client.get("/api/health", headers={"Origin": OTHER})
    assert "Access-Control-Allow-Origin" not in res.headers
    assert "Access-Control-Allow-Credentials" not in res.headers


@pytest.mark.parametrize("path", ["/api/health", "/api/ai/chat", "/API/AI/CHAT", "/api/books/a+b"])
def test_preflight_allows_the_client_headers_only_for_allowed_origins(client, path):
    headers = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type, authorization, x-api-key, x-request-id",
    }
    ok = client.options(path, headers={"Origin": ALLOWED, **headers})
    assert ok.headers.get("Access-Control-Allow-Origin") == ALLOWED
    allowed = {h.strip().lower() for h in ok.headers.get("Access-Control-Allow-Headers", "").split(",")}
    assert {"content-type", "authorization", "x-api-key", "x-request-id"} <= allowed

    denied = client.options(path, headers={"Origin": OTHER, **headers})
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_private_network_access_is_not_granted(client):
    res = client.options("/api/health", headers={
        "Origin": ALLOWED,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Private-Network": "true",
    })
    assert res.headers.get("Access-Control-Allow-Private-Network") != "true"
