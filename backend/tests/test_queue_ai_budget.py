"""Reloading the review queue cannot be used to make unlimited AI calls."""

import pytest
from backend.application.use_cases.learning_outcomes import GetReviewQueueUseCase
from backend.infrastructure.persistence.in_memory_learning_repository import (
    InMemoryLearningOutcomesRepository,
)
from backend.infrastructure.persistence.in_memory_note_repository import InMemoryNoteRepository

pytestmark = pytest.mark.unit


class Llm:
    def __init__(self):
        self.calls = 0

    def generate_response(self, system, user):
        self.calls += 1
        return "Why do habits compound?"


def test_queue_without_ai_budget_makes_no_call_and_creates_no_generic_card():
    notes, llm = InMemoryNoteRepository(), Llm()
    notes.create_note("u1", "b1", "key_takeaway", "Habits compound.")
    uc = GetReviewQueueUseCase(learning_repo=InMemoryLearningOutcomesRepository(), note_repo=notes, llm_port=llm)
    assert uc.execute("u1", allow_llm=False) == [] and llm.calls == 0
    assert len(uc.execute("u1")) == 1 and llm.calls == 1  # budget back: the card is written


def test_queue_route_passes_the_reader_budget():
    from pathlib import Path

    src = (Path(__file__).parent.parent / "routes" / "routes.py").read_text(encoding="utf-8")
    assert "allow_llm=_ai_budget_left(user_id)" in src
