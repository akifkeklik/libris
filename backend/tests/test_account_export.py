"""Full personal-data export: every section, paged past one page, honest about missing sources."""

import json

import pytest
from backend.app import create_app
from backend.application.use_cases.account_export import PAGE, ExportAccountDataUseCase

pytestmark = pytest.mark.unit


class Interactions:
    def get_user_profile(self, uid): return {"id": uid, "preferred_genres": ["History"]}
    def get_user_interactions(self, uid): return [{"book_id": "978", "interaction_type": "reading"}]
    def get_user_favorites(self, uid): return [{"book_id": "978", "book_title": "Dune"}]


class Notes:
    def __init__(self, n): self.rows = [{"id": f"n{i}", "book_id": "978", "note_type": "key_takeaway",
                                         "content": f"takeaway {i}", "created_at": "2026-11-01"} for i in range(n)]
    def get_user_notes(self, uid, limit=50, offset=0, **kw): return self.rows[offset:offset + limit]


class Reviews:
    def get_review_by_note_id(self, note_id, uid): return {"note_id": note_id, "interval_days": 3}


class BrokenLearning:  # e.g. review_items does not exist in this database
    def list_review_items(self, *a, **k): raise RuntimeError("relation review_items does not exist")
    def get_review_attempts(self, *a, **k): raise RuntimeError("relation review_attempts does not exist")


class Learning:
    def list_review_items(self, uid, status="active", limit=100, offset=0, **k):
        assert status is None, "export must include archived/suspended cards too"
        return [{"question": "What is stoicism?", "answer": "A philosophy"}][offset:offset + limit]
    def get_review_attempts(self, uid, limit=50, offset=0, **k):
        return [{"reviewed_at": "2026-11-02T10:00:00", "outcome": "good"}][offset:offset + limit]


def test_collects_every_section_and_pages_past_one_page():
    uc = ExportAccountDataUseCase(Interactions(), Notes(PAGE * 2 + 7), Reviews(), Learning())
    data = uc.collect("u1")
    assert len(data["notes"]) == PAGE * 2 + 7  # nothing silently truncated at one page
    assert len(data["note_reviews"]) == PAGE * 2 + 7
    assert data["review_cards"] and data["review_history"] and data["library"] and data["favorites"]
    assert data["profile"]["preferred_genres"] == ["History"]
    assert data["unavailable_sections"] == []


def test_a_missing_source_is_reported_not_hidden_and_the_rest_is_exported():
    data = ExportAccountDataUseCase(Interactions(), Notes(3), Reviews(), BrokenLearning()).collect("u1")
    assert sorted(data["unavailable_sections"]) == ["review_cards", "review_history"]
    assert len(data["notes"]) == 3 and data["review_cards"] == []


def test_json_and_markdown_outputs():
    uc = ExportAccountDataUseCase(Interactions(), Notes(2), Reviews(), Learning())
    js = uc.execute("u1", "json")
    assert js["filename"].endswith(".json") and json.loads(js["content"])["notes"][1]["content"] == "takeaway 1"
    md = uc.execute("u1", "markdown")["content"]
    for text in ("# Libris: my data", "takeaway 0", "What is stoicism?", "Dune", "Review history (1 attempts)"):
        assert text in md
    with pytest.raises(ValueError):
        uc.execute("u1", "pdf")


def test_export_endpoint_is_an_uncached_attachment(monkeypatch):
    from backend.routes import routes

    monkeypatch.setattr(routes.container, "export_account_uc",
                        ExportAccountDataUseCase(Interactions(), Notes(1), Reviews(), Learning()))
    app = create_app()
    app.config["TESTING"] = True

    @app.before_request
    def fake_auth():
        from flask import g
        g.user_id = "u1"

    res = app.test_client().get("/api/account/export?format=markdown")
    assert res.status_code == 200
    assert "attachment" in res.headers["Content-Disposition"] and res.headers["Cache-Control"] == "no-store, private"
    assert "takeaway 0" in res.get_data(as_text=True)
    assert app.test_client().get("/api/account/export?format=pdf").status_code == 400


def test_export_requires_authentication():
    app = create_app()
    app.config["TESTING"] = True
    app.config["ENFORCE_AUTH_IN_TESTS"] = True
    assert app.test_client().get("/api/account/export").status_code == 401
