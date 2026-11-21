"""
HTTP error contract: request size cap and status codes of werkzeug errors.

Before: no MAX_CONTENT_LENGTH (a 3 MiB JSON body to /api/ai/chat was read, parsed and answered
200), and the catch-all Exception handler also caught werkzeug HTTP errors, so 413/400/415 went
out as 500 "Internal server error" and were logged as unhandled exceptions.
"""

import json

import pytest
from backend.app import create_app
from backend.config import Config
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

pytestmark = pytest.mark.api

CAP = Config.MAX_REQUEST_BYTES


def _app(**config):
    app = create_app()
    app.config["TESTING"] = True
    app.config.update(config)

    @app.route("/api/_test/bad-request", methods=["POST"])
    def _bad_request():
        raise BadRequest()

    @app.route("/api/_test/unsupported", methods=["POST"])
    def _unsupported():
        raise UnsupportedMediaType()

    @app.route("/api/_test/boom", methods=["GET"])
    def _boom():
        raise RuntimeError("unexpected")

    return app


def _body(total_bytes):
    payload = {"query": "history books", "pad": ""}
    payload["pad"] = "y" * (total_bytes - len(json.dumps(payload)))
    data = json.dumps(payload)
    assert len(data.encode()) == total_bytes
    return data


def test_default_cap_is_one_mebibyte_and_applied():
    assert CAP == 1024 * 1024
    assert _app().config["MAX_CONTENT_LENGTH"] == CAP


def test_body_over_the_cap_is_rejected_with_413_json():
    res = _app().test_client().post("/api/ai/chat", data=_body(CAP + 1), content_type="application/json")
    assert res.status_code == 413
    assert res.get_json() == {"error": "Request body too large", "max_bytes": CAP}


def test_body_at_the_cap_is_not_rejected_for_size(monkeypatch):
    app = _app()
    # The route itself is not under test here; only that the size check lets the body through.
    seen = {}

    @app.route("/api/_test/echo-size", methods=["POST"])
    def _echo():
        from flask import request
        seen["n"] = len(request.get_data())
        return {"ok": True}

    res = app.test_client().post("/api/_test/echo-size", data=_body(CAP), content_type="application/json")
    assert res.status_code == 200 and seen["n"] == CAP


def test_cap_is_configurable():
    class Small(Config):
        MAX_REQUEST_BYTES = 2048

    app = create_app(Small)
    app.config["TESTING"] = True
    res = app.test_client().post("/api/ai/chat", data=_body(4096), content_type="application/json")
    assert res.status_code == 413 and res.get_json()["max_bytes"] == 2048


@pytest.mark.parametrize("path, status", [("/api/_test/bad-request", 400), ("/api/_test/unsupported", 415)])
def test_werkzeug_errors_keep_their_status(path, status):
    res = _app().test_client().post(path, json={})
    assert res.status_code == status
    assert res.is_json and res.get_json()["error"] != "Internal server error"


def test_404_and_405_messages_are_unchanged():
    client = _app().test_client()
    assert client.get("/api/does-not-exist").get_json() == {"error": "Resource not found"}
    res = client.delete("/api/health")
    assert res.status_code == 405 and res.get_json() == {"error": "Method not allowed"}


def test_unhandled_exceptions_are_still_500_with_a_request_id():
    res = _app().test_client().get("/api/_test/boom", headers={"X-Request-Id": "req-123"})
    assert res.status_code == 500
    assert res.get_json() == {"error": "Internal server error", "request_id": "req-123"}


def test_authentication_runs_before_the_body_is_read():
    # An unauthenticated client cannot make the server parse a large body: 401 comes first.
    client = _app(ENFORCE_AUTH_IN_TESTS=True).test_client()
    res = client.post("/api/ai/chat", data=_body(CAP + 1), content_type="application/json")
    assert res.status_code == 401
