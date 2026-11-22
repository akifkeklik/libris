"""Faz 3 reminders: preferences, e-mail content, the hourly worker, endpoints and the Resend adapter.
The SQL side (candidates, idempotent send log, RLS, worker role) is backend/tests/sql/test_17_reminders.sql."""

import datetime
import logging
from unittest.mock import MagicMock

import pytest
from backend.app import create_app
from backend.application.use_cases.reminders import (
    ReminderPreferencesUseCase,
    build_reminder_email,
    validate_preferences,
)
from backend.infrastructure.email.resend_adapter import (
    EmailMessage,
    EmailSendError,
    FakeEmailAdapter,
    ResendEmailAdapter,
)
from backend.scripts.send_reminders import run

pytestmark = pytest.mark.unit

CAND = {"user_id": "u1", "email": "reader@example.com", "language": "tr", "local_date": datetime.date(2026, 11, 23),
        "unsubscribe_token": "5f0c6d2e-1111-4222-8333-944455556666", "due_count": 3,
        "first_question": "Orwell neden <gözetim> konusunu seçti?"}


# ── Preferences ──────────────────────────────────────────────────────────────

def test_validate_preferences_accepts_and_normalizes():
    out = validate_preferences({"channel": "email", "local_time": "07:30", "timezone": "Europe/Istanbul",
                                "quiet_days": [6, 0, 6], "language": "tr"})
    assert out == {"channel": "email", "local_time": "07:30", "timezone": "Europe/Istanbul", "quiet_days": [0, 6], "language": "tr"}


@pytest.mark.parametrize("bad", [{"channel": "sms"}, {"local_time": "25:00"}, {"local_time": "9am"},
                                 {"timezone": "Mars/Olympus"}, {"quiet_days": [7]}, {"quiet_days": [True]},
                                 {"quiet_days": "0,6"}, {"language": "pt"}])
def test_validate_preferences_rejects(bad):
    with pytest.raises(ValueError):
        validate_preferences(bad)


def test_email_comes_from_the_session_not_the_body():
    repo = MagicMock()
    ReminderPreferencesUseCase(repo).update("u1", "jwt", "real@example.com", {"email": "attacker@example.com"})
    saved = repo.upsert.call_args.args[2]
    assert saved["email"] == "real@example.com"


def test_defaults_before_first_save():
    repo = MagicMock()
    repo.get.return_value = None
    prefs = ReminderPreferencesUseCase(repo).get("u1", "jwt")
    assert prefs["channel"] == "email" and prefs["local_time"] == "09:00" and prefs["saved"] is False


# ── E-mail content ───────────────────────────────────────────────────────────

def test_email_is_in_the_readers_language_with_count_time_first_question_and_links():
    mail = build_reminder_email(CAND, "https://libris.app", "https://api.libris.app")
    assert mail.subject == "Seni bekleyen 3 soru var"
    assert "Yaklaşık 2 dakika" in mail.text and "Orwell neden" in mail.text
    assert "https://libris.app/learning?utm_source=reminder&reminder_date=2026-11-23" in mail.text
    assert mail.headers["List-Unsubscribe"] == "<https://api.libris.app/api/reminders/unsubscribe?token=5f0c6d2e-1111-4222-8333-944455556666>"
    assert mail.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "&lt;gözetim&gt;" in mail.html and "<gözetim>" not in mail.html  # the question is escaped


def test_english_singular_and_unknown_language_falls_back_to_english():
    mail = build_reminder_email({**CAND, "language": "xx", "due_count": 1, "first_question": None}, "https://a", "https://b")
    assert mail.subject == "1 question waiting for you" and "About 1 minute." in mail.text and "First question" not in mail.text


# ── Worker ───────────────────────────────────────────────────────────────────

class Store:
    def __init__(self, candidates, taken=()):
        self.cands, self.claims, self.released, self.taken = candidates, [], [], set(taken)

    def candidates(self, now):
        return list(self.cands)

    def claim(self, c):
        if c["user_id"] in self.taken:
            return False
        self.taken.add(c["user_id"])
        self.claims.append(c["user_id"])
        return True

    def release(self, c):
        self.taken.discard(c["user_id"])
        self.released.append(c["user_id"])


def test_worker_sends_once_and_skips_already_claimed(caplog):
    store = Store([CAND, {**CAND, "user_id": "u2", "email": "two@example.com"}], taken={"u2"})
    mail = FakeEmailAdapter()
    with caplog.at_level(logging.INFO):
        stats = run(store, mail, "https://a", "https://b")
    assert stats == {"candidates": 2, "sent": 1, "skipped": 1, "failed": 0, "permanent_failures": 0}
    assert [m.to for m in mail.sent] == ["reader@example.com"]
    assert "reader@example.com" not in caplog.text and "Orwell" not in caplog.text


def test_retryable_failure_releases_the_claim_permanent_failure_keeps_it():
    class Port:
        def send(self, m):
            raise EmailSendError("x", 503 if m.to == "reader@example.com" else 422, retryable=m.to == "reader@example.com")
    store = Store([CAND, {**CAND, "user_id": "u2", "email": "bad@example"}])
    stats = run(store, Port(), "https://a", "https://b")
    assert store.released == ["u1"] and "u2" in store.taken
    assert stats["failed"] == 1 and stats["permanent_failures"] == 1


def test_dry_run_claims_nothing():
    store = Store([CAND])
    mail = FakeEmailAdapter()
    stats = run(store, mail, "https://a", "https://b", dry_run=True)
    assert stats["sent"] == 1 and store.claims == [] and len(mail.sent) == 1


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    from backend.routes import routes
    repo = MagicMock()
    repo.get.return_value = None
    repo.unsubscribe.side_effect = lambda token: token == CAND["unsubscribe_token"]
    monkeypatch.setattr(routes.container, "reminder_repo", repo, raising=False)
    monkeypatch.setattr(routes.container, "reminder_prefs_uc", ReminderPreferencesUseCase(repo), raising=False)
    from backend.config import Config
    monkeypatch.setattr(Config, "APP_URL", "https://libris.app")
    a = create_app()
    a.config["TESTING"] = True
    a.config["ENFORCE_AUTH_IN_TESTS"] = True
    return a, repo


def test_unsubscribe_link_works_without_login(app):
    a, repo = app
    c = a.test_client()
    res = c.get(f"/api/reminders/unsubscribe?token={CAND['unsubscribe_token']}")
    assert res.status_code == 303 and res.headers["Location"] == "https://libris.app/reminders/unsubscribed?status=ok"
    assert c.get("/api/reminders/unsubscribe?token=not-a-uuid").headers["Location"].endswith("status=invalid")
    assert c.post(f"/api/reminders/unsubscribe?token={CAND['unsubscribe_token']}").get_json() == {"unsubscribed": True}
    repo.unsubscribe.assert_called_with(CAND["unsubscribe_token"])


def test_preferences_require_login(app):
    a, _ = app
    assert a.test_client().get("/api/reminders/preferences").status_code == 401


# ── Resend adapter ───────────────────────────────────────────────────────────

def test_resend_adapter_payload_and_errors():
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=200, json=lambda: {"id": "em_1"})
    port = ResendEmailAdapter("re_test_key", "Libris <r@libris.app>", session=session)
    assert port.send(EmailMessage("a@b.co", "S", "<p>h</p>", "t", {"List-Unsubscribe": "<x>"})) == "em_1"
    kwargs = session.post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    assert kwargs["json"]["to"] == ["a@b.co"] and kwargs["json"]["headers"] == {"List-Unsubscribe": "<x>"}
    for status, retryable in ((429, True), (503, True), (422, False)):
        session.post.return_value = MagicMock(status_code=status, json=lambda: {"name": "err"})
        with pytest.raises(EmailSendError) as err:
            port.send(EmailMessage("a@b.co", "S", "h", "t"))
        assert err.value.retryable is retryable and "re_test_key" not in str(err.value)


# ── Web Push and product events ──────────────────────────────────────────────

from backend.application.use_cases.reminders import (  # noqa: E402
    build_reminder_push,
    validate_event,
    validate_push_subscription,
)
from backend.infrastructure.push.webpush_adapter import FakePushAdapter  # noqa: E402

SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "B" + "x" * 86, "auth": "a" * 22}}


def test_push_subscription_validation():
    assert validate_push_subscription(SUB) == {"endpoint": SUB["endpoint"], "p256dh": "B" + "x" * 86, "auth": "a" * 22}
    for bad in ({**SUB, "endpoint": "http://x"}, {**SUB, "keys": {"p256dh": "short", "auth": "a" * 22}},
                {**SUB, "keys": {"p256dh": "B" + "x" * 86, "auth": "bad auth!"}}, {"endpoint": SUB["endpoint"]}, []):
        with pytest.raises(ValueError):
            validate_push_subscription(bad)


def test_push_payload_has_count_and_link_but_never_the_question():
    p = build_reminder_push(CAND, "https://libris.app")
    assert p["title"] == "Seni bekleyen 3 soru var" and p["body"] == "Yaklaşık 2 dakika."
    assert p["url"] == "https://libris.app/learning?utm_source=reminder&reminder_channel=push&reminder_date=2026-11-23"
    assert "Orwell" not in str(p)


def test_events_are_whitelisted_with_small_typed_props():
    assert validate_event({"event": "reminder_opened", "props": {"channel": "push", "reminder_date": "2026-11-23"}}) == \
        {"event": "reminder_opened", "props": {"channel": "push", "reminder_date": "2026-11-23"}}
    assert validate_event({"event": "review_session_completed", "props": {"reviewed_count": 7, "extra": "x"}}) == \
        {"event": "review_session_completed", "props": {"reviewed_count": 7}}
    for bad in ({"event": "page_view"}, {"event": "reminder_opened", "props": {"channel": "sms"}},
                {"event": "reminder_opened", "props": {"reminder_date": "<script>"}},
                {"event": "review_session_completed", "props": {"reviewed_count": True}}):
        with pytest.raises(ValueError):
            validate_event(bad)


class PushStore(Store):
    def __init__(self, push, subs):
        super().__init__([])
        self.push, self.subs, self.deleted = push, subs, []

    def push_candidates(self, now):
        return [{**c, "channel": "push"} for c in self.push]

    def subscriptions(self, user_id):
        return list(self.subs.get(user_id, []))

    def delete_subscription(self, endpoint):
        self.deleted.append(endpoint)


def _sub(ep):
    return {"endpoint": ep, "p256dh": "k", "auth": "s"}


def test_push_goes_to_every_device_once_and_gone_devices_are_deleted():
    store = PushStore([CAND, {**CAND, "user_id": "u2"}, {**CAND, "user_id": "u3"}],
                      {"u1": [_sub("https://p/1a"), _sub("https://p/1b")], "u2": [_sub("https://p/2")]})
    port = FakePushAdapter(gone={"https://p/1b", "https://p/2"})
    stats = run(store, None, "https://a", "https://b", push_port=port)
    assert [ep for ep, _ in port.sent] == ["https://p/1a"]
    assert store.deleted == ["https://p/1b", "https://p/2"]
    assert stats["push_sent"] == 1 and stats["push_gone"] == 2 and stats["push_skipped"] == 1  # u3: no device
    assert stats["push_failed"] == 1 and store.released == []  # u2: only device gone -> nothing to retry
    assert stats["candidates"] == 0  # e-mail channel not configured -> skipped entirely


def test_push_temporary_failure_releases_the_claim_for_the_next_hour():
    store = PushStore([CAND], {"u1": [_sub("https://p/1")]})
    stats = run(store, None, "https://a", "https://b", push_port=FakePushAdapter(fail={"https://p/1": True}))
    assert store.released == ["u1"] and stats["push_failed"] == 1


def test_push_endpoints_and_events_routes(app):
    a, repo = app
    c = a.test_client()
    assert c.post("/api/reminders/push-subscription", json=SUB).status_code == 401
    assert c.post("/api/events", json={"event": "reminder_opened"}).status_code == 401
    assert c.get("/api/reminders/push-key").status_code == 401
