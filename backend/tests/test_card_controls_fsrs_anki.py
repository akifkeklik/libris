"""Faz 5: card controls (edit / regenerate / report), FSRS behind the flag, retention setting,
Anki export. SQL side of the settings table: backend/tests/sql/test_20_learning_settings.sql."""

import datetime
import io
import sqlite3
import tempfile
import zipfile

import pytest
from backend.application.use_cases.card_controls import (
    MAX_REGENERATIONS,
    CardControlsUseCase,
    build_apkg,
    clean_item_updates,
)
from backend.application.use_cases.fsrs_scheduling import FsrsScheduler
from backend.application.use_cases.learning_outcomes import (
    GetReviewQueueUseCase,
    SubmitReviewAttemptUseCase,
    UpdateReviewItemUseCase,
)
from backend.infrastructure.persistence.in_memory_import_repository import (
    InMemoryLearningSettingsRepository,
)
from backend.infrastructure.persistence.in_memory_learning_repository import (
    InMemoryLearningOutcomesRepository,
)

pytestmark = pytest.mark.unit
U = "user-1"
T0 = datetime.datetime(2026, 1, 1, 9, tzinfo=datetime.timezone.utc)


class Llm:
    def __init__(self, reply="Why do habits compound over time?"):
        self.reply, self.calls = reply, 0

    def generate_response(self, system, user):
        self.calls += 1
        return self.reply


def _item(repo, question="Q?", answer="Habits compound."):
    return repo.create_review_item(user_id=U, title="T", concept="Atomic Habits", question=question, answer=answer,
                                   explanation="", source_type="key_takeaway", source_id="n1", book_id="b1")


def _controls(llm=None, fsrs=False):
    repo = InMemoryLearningOutcomesRepository()
    queue = GetReviewQueueUseCase(learning_repo=repo, llm_port=llm)
    return CardControlsUseCase(repo, queue, InMemoryLearningSettingsRepository(), fsrs_enabled=fsrs), repo


# ── Edit: only card content ──────────────────────────────────────────────────

def test_edit_accepts_content_and_rejects_schedule_fields():
    assert clean_item_updates({"question": " New? ", "status": "paused"}) == {"question": "New?", "status": "paused"}
    for bad in ({"stage": 5}, {"next_review_at": "2099-01-01"}, {"user_id": "someone"}, {"question": ""},
                {"question": "x" * 501}, {"status": "deleted"}, {"answer": 3}, {}):
        with pytest.raises(ValueError):
            clean_item_updates(bad)


def test_old_update_endpoint_use_case_no_longer_writes_schedule_or_counters():
    repo = InMemoryLearningOutcomesRepository()
    item = _item(repo)
    with pytest.raises(ValueError):
        UpdateReviewItemUseCase(repo).execute(U, item["id"], {"question": "ok?", "total_reviews": 999})
    updated = UpdateReviewItemUseCase(repo).execute(U, item["id"], {"question": "Better question?"})
    assert updated["question"] == "Better question?" and updated["total_reviews"] == 0


# ── Regenerate / report ──────────────────────────────────────────────────────

def test_regenerate_uses_one_llm_call_keeps_history_and_is_limited():
    llm = Llm()
    uc, repo = _controls(llm)
    item = _item(repo)
    out = uc.regenerate(U, item["id"])
    assert out["question"] == "Why do habits compound over time?" and llm.calls == 1
    assert out["metadata"]["previous_questions"] == ["Q?"] and out["metadata"]["regenerations"] == 1
    repo.update_review_item(item["id"], U, {"metadata": {**out["metadata"], "regenerations": MAX_REGENERATIONS}})
    with pytest.raises(PermissionError):
        uc.regenerate(U, item["id"])


def test_regenerate_without_llm_or_with_useless_output_is_an_error_not_a_generic_card():
    uc, repo = _controls(None)
    item = _item(repo)
    with pytest.raises(RuntimeError):
        uc.regenerate(U, item["id"])
    uc2, repo2 = _controls(Llm(reply="Here is a summary."))
    item2 = _item(repo2)
    with pytest.raises(RuntimeError):
        uc2.regenerate(U, item2["id"])
    assert repo2.get_review_item_by_id(item2["id"], U)["question"] == "Q?"


def test_report_archives_with_reason_and_other_users_cannot_touch_the_card():
    uc, repo = _controls()
    item = _item(repo)
    with pytest.raises(ValueError):
        uc.report(U, item["id"], "boring")
    uc.report(U, item["id"], "wrong", "The answer is about another chapter." * 20)
    stored = repo.get_review_item_by_id(item["id"], U)
    assert stored["status"] == "archived" and stored["metadata"]["report"]["reason"] == "wrong"
    assert len(stored["metadata"]["report"]["comment"]) == 300
    with pytest.raises(LookupError):
        uc.report("someone-else", item["id"], "wrong")


# ── Settings ─────────────────────────────────────────────────────────────────

def test_retention_setting_defaults_validates_and_persists():
    uc, _ = _controls(fsrs=True)
    assert uc.get_settings(U, None) == {"fsrs_enabled": True, "desired_retention": 0.9}
    for bad in (0.5, 0.99, "x", None):
        with pytest.raises(ValueError):
            uc.save_settings(U, None, {"desired_retention": bad})
    assert uc.save_settings(U, None, {"desired_retention": 0.85})["desired_retention"] == 0.85
    assert uc.retention_for(U, None) == 0.85


# ── FSRS ─────────────────────────────────────────────────────────────────────

def test_fsrs_is_off_by_default_and_policy_v1_is_unchanged():
    repo = InMemoryLearningOutcomesRepository()
    item = _item(repo)
    out = SubmitReviewAttemptUseCase(repo).execute(U, item["id"], "remembered", as_of=T0)
    assert out["interval_days"] == 3 and "fsrs" not in (out["item"].get("metadata") or {})


def test_fsrs_schedules_in_days_stores_state_and_honours_retention():
    repo = InMemoryLearningOutcomesRepository()
    item = _item(repo)
    uc = SubmitReviewAttemptUseCase(repo, fsrs_enabled=True, retention_for=lambda uid: 0.9)
    first = uc.execute(U, item["id"], "remembered", as_of=T0)
    assert first["item"]["metadata"]["scheduler"] == "fsrs" and "fsrs" in first["item"]["metadata"]
    second = uc.execute(U, item["id"], "remembered", as_of=T0 + datetime.timedelta(days=first["interval_days"]))
    assert second["interval_days"] > first["interval_days"]  # successful recall -> longer gap
    lapse = uc.execute(U, item["id"], "struggled", as_of=T0 + datetime.timedelta(days=30))
    assert 1 <= lapse["interval_days"] < second["interval_days"]
    # Higher target retention -> shorter intervals for the same history.
    hist = [{"outcome": "remembered", "reviewed_at": "2026-01-01T09:00:00+00:00"},
            {"outcome": "remembered", "reviewed_at": "2026-01-05T09:00:00+00:00"}]
    base = {"created_at": "2025-12-31T09:00:00+00:00"}
    when = datetime.datetime(2026, 1, 20, tzinfo=datetime.timezone.utc)
    assert FsrsScheduler(0.95).review(base, hist, "remembered", when)[2] < FsrsScheduler(0.85).review(base, hist, "remembered", when)[2]


def test_fsrs_rebuilds_a_card_from_existing_review_attempts():
    repo = InMemoryLearningOutcomesRepository()
    item = _item(repo)
    v1 = SubmitReviewAttemptUseCase(repo)
    for k in range(3):  # history recorded under Policy v1, before the flag was switched on
        v1.execute(U, item["id"], "remembered", as_of=T0 + datetime.timedelta(days=10 * k))
    with_history = SubmitReviewAttemptUseCase(repo, fsrs_enabled=True).execute(
        U, item["id"], "remembered", as_of=T0 + datetime.timedelta(days=40))
    fresh = _item(repo, question="Other?")
    without = SubmitReviewAttemptUseCase(repo, fsrs_enabled=True).execute(
        U, fresh["id"], "remembered", as_of=T0 + datetime.timedelta(days=40))
    assert with_history["interval_days"] > without["interval_days"]  # earlier learning is not reset


def test_fsrs_failure_falls_back_to_policy_v1():
    repo = InMemoryLearningOutcomesRepository()
    item = _item(repo)

    def broken(uid):
        raise RuntimeError("settings store down")

    out = SubmitReviewAttemptUseCase(repo, fsrs_enabled=True, retention_for=broken).execute(U, item["id"], "remembered", as_of=T0)
    assert out["interval_days"] == 3


# ── Anki ─────────────────────────────────────────────────────────────────────

def test_anki_package_has_every_card_escaped_with_stable_ids_and_leaves_no_temp_file():
    items = [{"id": "i1", "question": "What is <b>x</b>?", "answer": "line1\nline2", "concept": "Book"},
             {"id": "i2", "question": "Q2?", "answer": "A2", "concept": "Book"}]
    before = set(__import__("os").listdir(tempfile.gettempdir()))
    data = build_apkg(items, timestamp=1_700_000_000)
    after = set(__import__("os").listdir(tempfile.gettempdir()))
    assert not [f for f in after - before if f.endswith(".anki2")]
    z = zipfile.ZipFile(io.BytesIO(data))
    assert set(z.namelist()) == {"collection.anki2", "media"}
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as fh:
        fh.write(z.read("collection.anki2"))
    conn = sqlite3.connect(fh.name)
    rows = conn.execute("select guid, flds from notes order by id").fetchall()
    conn.close()
    __import__("os").remove(fh.name)
    assert len(rows) == 2
    assert "What is &lt;b&gt;x&lt;/b&gt;?" in rows[0][1] and "line1<br>line2" in rows[0][1]
    assert build_apkg(items[:1], timestamp=1_700_000_500) and rows[0][0] == _guid_of(items[0])


def _guid_of(item):
    import genanki

    return genanki.guid_for("libris", item["id"])


def test_card_control_endpoints_require_login(monkeypatch):
    from backend.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["ENFORCE_AUTH_IN_TESTS"] = True
    c = app.test_client()
    assert c.post("/api/learning/items/x/regenerate").status_code == 401
    assert c.post("/api/learning/items/x/report", json={"reason": "wrong"}).status_code == 401
    assert c.get("/api/learning/settings").status_code == 401
    assert c.get("/api/learning/export/anki").status_code == 401


def test_a_reported_card_is_not_recreated_from_its_note_on_the_next_queue_load():
    from backend.infrastructure.persistence.in_memory_note_repository import InMemoryNoteRepository

    notes = InMemoryNoteRepository()
    notes.create_note(U, "b1", "key_takeaway", "Habits compound.")
    repo = InMemoryLearningOutcomesRepository()
    queue = GetReviewQueueUseCase(learning_repo=repo, note_repo=notes)
    first = queue.execute(U)
    assert len(first) == 1
    CardControlsUseCase(repo, queue).report(U, first[0]["id"], "wrong")
    assert queue.execute(U) == []  # the note stays, the reported card does not come back
    assert queue.create_item_for_note(U, notes.get_user_notes(U, limit=5)[0])["status"] == "archived"
