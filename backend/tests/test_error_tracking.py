"""
Sentry error tracking: off without SENTRY_DSN, and no user data in what would be sent.

The end-to-end tests run the real sentry-sdk with a capturing transport (no network): a request
carrying a note, an e-mail, tokens, cookies and a search query fails, and the captured payload
must contain none of them.
"""

import json

import pytest

sentry_sdk = pytest.importorskip("sentry_sdk")

from backend.infrastructure.logging.error_tracking import (  # noqa: E402
    init_error_tracking,
    scrub_breadcrumb,
    scrub_event,
)
from flask import Flask, request  # noqa: E402
from sentry_sdk.transport import Transport  # noqa: E402

pytestmark = pytest.mark.unit

# Built at runtime: Sentry attaches source-code context lines, so literals in this file would
# show up in the payload as code, not as leaked user data.
NOTE = " ".join(["My", "private", "reading", "note", "about", "grief"])
EMAIL = "reader.private" + "@" + "example.com"
QUERY = "+".join(["grief", "and", "my", "mother"])
SECRETS = ("Bearer user-jwt-token", "server-api-key", "session=abc123")


class CaptureTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.payloads = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            self.payloads.append(item.payload.get_bytes().decode("utf-8", "replace"))


@pytest.fixture
def captured():
    transport = CaptureTransport()
    started = init_error_tracking({"SENTRY_DSN": "https://public@o0.ingest.sentry.io/0"}, transport=transport,
                                  default_integrations=True)
    assert started
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # back to a no-op client so other tests send nothing


def test_disabled_without_dsn():
    assert init_error_tracking({}) is False
    assert init_error_tracking({"SENTRY_DSN": "   "}) is False


def test_failing_request_sends_no_user_data(captured):
    app = Flask(__name__)

    @app.route("/api/notes", methods=["POST"])
    def notes():
        body = request.get_json()
        raise ValueError(f"could not save note {body['content']} for {body['email']}")

    app.test_client().post(
        "/api/notes?q=" + QUERY,
        json={"content": NOTE, "email": EMAIL},
        headers={"Authorization": SECRETS[0], "X-Api-Key": SECRETS[1], "Cookie": SECRETS[2],
                 "X-Request-Id": "req-1"},
    )
    sentry_sdk.flush(2)
    sent = "\n".join(captured.payloads)
    assert "ValueError" in sent, "the error itself must still be reported"
    for leaked in (NOTE, EMAIL, QUERY, *SECRETS, "user-jwt-token"):
        assert leaked not in sent, f"leaked to Sentry: {leaked!r}"
    assert "[redacted]" in sent  # the exception message was removed, its type and stack kept


def test_logged_errors_and_breadcrumbs_are_scrubbed(captured):
    import logging

    log = logging.getLogger("libris.test")
    # Production's setup_logger() makes INFO lines breadcrumbs; set it here so the test does not
    # depend on which test configured logging first (this is how the leak was found).
    log.setLevel(logging.INFO)
    log.info("user %s opened note: %s", EMAIL, NOTE)  # becomes a breadcrumb
    log.error("sync failed for %s", EMAIL)            # becomes an event
    sentry_sdk.flush(2)
    sent = "\n".join(captured.payloads)
    assert "sync failed" in sent and "opened note" in sent  # templates kept
    assert EMAIL not in sent
    assert NOTE not in sent


def test_scrub_event_unit():
    event = {
        "user": {"id": "u1", "email": EMAIL, "ip_address": "1.2.3.4"},
        "request": {"method": "POST", "url": "https://api/x?q=secret", "data": {"content": NOTE},
                    "cookies": {"s": "1"}, "env": {"REMOTE_ADDR": "1.2.3.4"},
                    "headers": {"Authorization": "Bearer t", "User-Agent": "ua", "X-Api-Key": "k"}},
        "extra": {"request_id": "r1", "extra_data": {"query": NOTE}},
        "exception": {"values": [{"value": f"bad {EMAIL}", "stacktrace": {"frames": [{"vars": {"note": NOTE}}]}}]},
        "logentry": {"message": f"x {EMAIL}", "params": [NOTE]},
    }
    out = json.dumps(scrub_event(event))
    for leaked in (NOTE, EMAIL, "secret", "Bearer t", '"k"', "1.2.3.4"):
        assert leaked not in out, leaked
    assert event["request"] == {"method": "POST", "url": "https://api/x", "headers": {"User-Agent": "ua"}}
    assert event["extra"] == {"request_id": "r1"} and event["user"] == {}


def test_long_text_is_truncated_and_breadcrumb_data_dropped():
    crumb = scrub_breadcrumb({"message": "x" * 1000, "data": {"body": NOTE}})
    assert "data" not in crumb and crumb["message"].endswith("[truncated]") and len(crumb["message"]) < 320
