"""Faz 4 imports: parsers, hashing, matching, the approval queue use case and the endpoints.
SQL side (dedup constraint, RLS, cap, cascade): backend/tests/sql/test_19_import_queue.sql."""

import uuid

import pytest
from backend.application.use_cases.imports import (
    MAX_PENDING_PER_USER,
    ImportUseCase,
    ParsedItem,
    best_match,
    content_hash,
    normalize_title,
    parse,
)
from backend.application.use_cases.learning_notes import CreateNoteUseCase
from backend.application.use_cases.learning_outcomes import GetReviewQueueUseCase
from backend.infrastructure.persistence.in_memory_import_repository import InMemoryImportRepository
from backend.infrastructure.persistence.in_memory_learning_repository import (
    InMemoryLearningOutcomesRepository,
)
from backend.infrastructure.persistence.in_memory_note_repository import InMemoryNoteRepository

pytestmark = pytest.mark.unit

KINDLE = (
    "﻿Atomic Habits (James Clear)\r\n- Your Highlight on page 27 | Location 410-412 | Added on Monday, 3 June 2024\r\n\r\n"
    "Habits are the compound interest of self-improvement.\r\n==========\r\n"
    "Atomic Habits (James Clear)\r\n- Your Bookmark on page 30 | Location 455 | Added on Monday, 3 June 2024\r\n\r\n\r\n==========\r\n"
    "Atomic Habits (James Clear)\r\n- Your Note on page 27 | Location 412 | Added on Monday, 3 June 2024\r\n\r\n"
    "Try this with reading.\r\n==========\r\n"
    "Der Prozess (Kafka, Franz)\r\n- Ihre Markierung bei Position 120-121 | Hinzugefügt am Montag\r\n\r\n"
    "Jemand musste Josef K. verleumdet haben.\r\n==========\r\n"
    "Some Book (A)\r\n- Your Highlight on page 5 | Location 50\r\n\r\n<You have reached the clipping limit for this item>\r\n==========\r\n"
    "Atomic Habits (James Clear)\r\n- Your Highlight on page 27 | Location 410-412 | Added on Tuesday, 4 June 2024\r\n\r\n"
    "Habits are the compound interest of self-improvement.\r\n==========\r\n"
)

READWISE = (
    "Highlight,Book Title,Book Author,Amazon Book ID,Note,Color,Tags,Location Type,Location,Highlighted at,Document tags\n"
    '"Habits are the compound interest of self-improvement.",Atomic Habits,James Clear,B01,"",yellow,,location,410,2024-06-03,\n'
    '"A quote with ""quotes""\nand a second line",Dune,Frank Herbert,B02,"my thought",,,page,12,2024-06-03,\n'
)

GOODREADS = (
    "Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,Average Rating,Publisher,Binding,"
    "Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,Bookshelves,"
    "Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies\n"
    '1,Dune,Frank Herbert,"Herbert, Frank",,="0441172717",="9780441172719",5,4.2,Ace,Paperback,604,1990,1965,'
    '2024/01/02,2023/12/01,,,read,"Loved the ecology.",,,1,0\n'
    '2,"Atomic Habits: An Easy & Proven Way",James Clear,"Clear, James",,="",="",0,4.4,Avery,Hardcover,320,2018,2018,'
    ',2024/02/01,to-read,to-read (#1),to-read,,,,0,0\n'
    "3,Some Book,Someone,,,,,0,3.9,X,Kindle,100,2001,2001,,2024/02/01,did-not-finish,,did-not-finish,,,,0,0\n"
)


# ── Parsers ──────────────────────────────────────────────────────────────────

def test_kindle_highlights_notes_bookmarks_languages_bom_crlf():
    res = parse("kindle", KINDLE)
    kinds = [(i.kind, i.book_title, i.book_author) for i in res.items]
    assert kinds[0] == ("highlight", "Atomic Habits", "James Clear")
    assert ("note", "Atomic Habits", "James Clear") in kinds
    assert ("highlight", "Der Prozess", "Kafka, Franz") in kinds
    assert res.skipped == 2  # the bookmark and Kindle's clipping-limit placeholder
    assert res.items[0].location.lower().startswith("location 410")
    assert res.items[0].content == "Habits are the compound interest of self-improvement."


def test_readwise_quoted_multiline_and_note_rows():
    res = parse("readwise", READWISE)
    assert [i.kind for i in res.items] == ["highlight", "highlight", "note"]
    assert res.items[1].content == 'A quote with "quotes"\nand a second line'
    assert res.items[2].content == "my thought" and res.items[2].book_title == "Dune"


def test_goodreads_shelves_isbn_rating_and_review():
    res = parse("goodreads", GOODREADS)
    shelves = [i for i in res.items if i.kind == "shelf"]
    assert [(s.book_title, s.shelf, s.isbn13, s.rating) for s in shelves] == [
        ("Dune", "finished", "9780441172719", 5), ("Atomic Habits: An Easy & Proven Way", "want_to_read", "", None)]
    assert any(i.kind == "note" and i.content == "Loved the ecology." for i in res.items)
    assert res.skipped == 1  # custom shelf without an equivalent


@pytest.mark.parametrize("source,text", [("readwise", GOODREADS), ("goodreads", READWISE), ("kindle", "   "), ("pdf", "x")])
def test_wrong_or_empty_files_are_explained(source, text):
    with pytest.raises(ValueError):
        parse(source, text)


def test_same_highlight_from_kindle_and_readwise_has_the_same_hash():
    k = parse("kindle", KINDLE).items[0]
    r = parse("readwise", READWISE).items[0]
    assert content_hash(k) == content_hash(r)
    assert content_hash(k) != content_hash(ParsedItem("note", k.book_title, content=k.content))


def test_title_normalisation_and_conservative_matching():
    assert normalize_title("The Hobbit (Middle-earth #1)") == normalize_title("Hobbit: There and Back Again")
    cands = [{"isbn13": "1", "title": "Atomic Habits", "authors": "Someone Else"},
             {"isbn13": "2", "title": "Atomic Habits", "authors": "James Clear"}]
    assert best_match("Atomic Habits: An Easy & Proven Way", "James Clear", cands) == "2"
    assert best_match("Atomic Habits", "", cands) == "1"
    assert best_match("Atomic", "James Clear", cands) is None  # partial titles never match


# ── Use case with in-memory parts ────────────────────────────────────────────

Repo = InMemoryImportRepository


class Catalog:
    def __init__(self):
        self.queries = []

    def search_books(self, query, limit=10):
        self.queries.append(query)
        return [{"isbn13": "9780735211292", "title": "Atomic Habits", "authors": "James Clear"}] if "Atomic" in query else []


class Feedback:
    def __init__(self):
        self.calls = []

    def execute(self, user_id, book_id, interaction, **kw):
        self.calls.append((book_id, interaction))
        return {"status": "success"}


class Llm:
    def __init__(self):
        self.calls = 0

    def generate_response(self, system, user):
        self.calls += 1
        return "What compounds over time?"


def _uc(llm=None):
    notes = InMemoryNoteRepository()
    review = GetReviewQueueUseCase(learning_repo=InMemoryLearningOutcomesRepository(), note_repo=notes, llm_port=llm)
    repo, cat, fb = Repo(), Catalog(), Feedback()
    return ImportUseCase(repo, cat, CreateNoteUseCase(notes), review_queue_uc=review, feedback_uc=fb), repo, cat, fb, notes


def test_import_dedups_within_file_and_across_imports_and_matches_once_per_book():
    uc, repo, cat, _, _ = _uc()
    first = uc.import_text("u1", "t", "kindle", KINDLE)
    assert first["parsed"] == 4 and first["new"] == 3 and first["duplicates"] == 1 and first["skipped"] == 2
    assert first["books"] == 2 and first["books_matched"] == 1
    assert len(cat.queries) == 2  # one catalogue lookup per distinct book
    again = uc.import_text("u1", "t", "readwise", READWISE)  # Atomic Habits highlight already queued
    assert again["new"] == 2 and again["duplicates"] == 1


def test_full_queue_is_refused_with_a_clear_message():
    uc, repo, _, _, _ = _uc()
    repo.count_pending = lambda *a: MAX_PENDING_PER_USER  # noqa: E731
    with pytest.raises(ValueError, match="queue is full"):
        uc.import_text("u1", "t", "kindle", KINDLE)


def test_approve_creates_notes_needs_a_book_and_stays_within_the_llm_budget():
    llm = Llm()
    uc, repo, _, _, notes = _uc(llm)
    many = "".join(f"Atomic Habits (James Clear)\n- Your Highlight on page {i} | Location {i}\n\nIdea number {i}.\n==========\n" for i in range(8))
    uc.import_text("u1", "t", "kindle", many + KINDLE)
    pending = {r["id"]: r for r in repo.list_pending("u1", "t", 100)}
    unmatched = [i for i, r in pending.items() if not r["book_id"]]
    matched = [i for i, r in pending.items() if r["book_id"]]
    out = uc.approve("u1", "t", list(pending))
    assert sorted(out["needs_book"]) == sorted(unmatched)
    assert out["approved"] == len(matched)
    assert llm.calls <= 5 and out["questions_created"] == 5 and out["questions_deferred"] == out["approved"] - 1 - 5
    # Kindle notes become personal notes (no question); highlights become takeaways.
    types = sorted(n["note_type"] for n in notes.get_user_notes("u1", limit=100))
    assert types.count("personal_note") == 1
    # The unmatched entry can be approved once the reader picks the book.
    out2 = uc.approve("u1", "t", unmatched, book_overrides={unmatched[0]: "9783150000001"})
    assert out2["approved"] == 1 and repo._rows[unmatched[0]]["book_id"] == "9783150000001"


def test_goodreads_shelves_go_to_the_library_and_reject_keeps_entries_out():
    uc, repo, _, fb, _ = _uc()
    uc.books = None
    uc.import_text("u1", "t", "goodreads", GOODREADS)
    rows = list(repo._rows.values())
    dune = next(r for r in rows if r["kind"] == "shelf" and r["book_title"] == "Dune")
    assert dune["book_id"] is None  # not in this test catalogue -> reader picks it
    uc.approve("u1", "t", [dune["id"]], book_overrides={dune["id"]: "9780441172719"})
    assert fb.calls == [("9780441172719", "finished")]
    other = [r["id"] for r in rows if r["status"] == "pending"]
    assert uc.reject("u1", "t", other) == len(other)
    assert uc.import_text("u1", "t", "goodreads", GOODREADS)["new"] == 0  # dismissed entries don't come back


@pytest.mark.parametrize("ids", [[], "x", ["not-a-uuid"], [str(uuid.uuid4())] * 101])
def test_decision_ids_are_validated(ids):
    uc, *_ = _uc()
    with pytest.raises(ValueError):
        uc.reject("u1", "t", ids)


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    from backend.app import create_app
    from backend.routes import routes

    uc, *_ = _uc()
    monkeypatch.setattr(routes.container, "import_uc", uc, raising=False)
    app = create_app()
    app.config["TESTING"] = True
    app.config["ENFORCE_AUTH_IN_TESTS"] = True
    return app.test_client()


def test_import_endpoints_require_login(client):
    assert client.post("/api/imports", json={"source": "kindle", "text": KINDLE}).status_code == 401
    assert client.get("/api/imports/pending").status_code == 401
    assert client.post("/api/imports/decide", json={"action": "reject", "ids": []}).status_code == 401


def test_import_body_may_exceed_the_general_limit_but_stays_bounded(monkeypatch):
    import json

    from backend.app import create_app
    from backend.routes import routes

    uc, *_ = _uc()
    monkeypatch.setattr(routes.container, "import_uc", uc, raising=False)
    app = create_app()
    app.config["TESTING"] = True

    @app.before_request
    def fake_auth():  # signed in, so the body limit itself is exercised
        from flask import g
        g.user_id = "u1"

    c = app.test_client()
    body = json.dumps({"source": "kindle", "text": "Book (A)\n- Your Highlight\n\n" + "x" * 2_000_000 + "\n=========="})
    assert c.post("/api/notes", data=body, content_type="application/json").status_code == 413
    assert c.post("/api/imports", data=body, content_type="application/json").status_code != 413
    huge = json.dumps({"source": "kindle", "text": "x" * (7 * 1024 * 1024)})
    assert c.post("/api/imports", data=huge, content_type="application/json").status_code == 413
