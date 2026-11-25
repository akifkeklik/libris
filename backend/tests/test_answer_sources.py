"""The books an answer uses lead its sources; optional AI calls have a per-reader limit."""

import pytest
from backend.application.use_cases.ai_rag import _used_books_first
from backend.routes import routes

pytestmark = pytest.mark.unit
BOOKS = [{"isbn13": "1", "title": "Philosophy For Dummies"}, {"isbn13": "2", "title": "Early Greek Philosophy"}]


def test_books_the_answer_uses_come_first_and_none_is_added_or_lost():
    assert _used_books_first("Try this one.", {"2": "why", "999": "invented"}, BOOKS) == [BOOKS[1], BOOKS[0]]
    assert _used_books_first("I suggest 'Philosophy For Dummies'.", {}, BOOKS) == BOOKS
    assert _used_books_first("Nothing fits well.", {}, BOOKS) == BOOKS


def test_optional_ai_calls_are_limited_per_reader():
    assert [routes._ai_budget_left("limit-test-reader") for _ in range(31)] == [True] * 30 + [False]
    assert routes._ai_budget_left("another-reader")
