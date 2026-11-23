"""
FSRS scheduling (Faz 5), behind the FSRS_ENABLED flag. Policy v1 (fixed 1/3/7/14/30-day stages)
stays the default and keeps running for everyone until the flag is on.

- Libris asks two things after a recall: remembered / struggled -> FSRS Good / Again.
- Intervals are whole days (no minute-long learning steps: reviews happen at most daily) and
  deterministic (no fuzzing), so the same history always gives the same schedule.
- The card state lives in review_items.metadata["fsrs"]. A card without state is built by
  replaying its review_attempts history first ("migration from review_attempts"), so switching
  the flag on never resets what a reader has already learned.
- desired_retention is the reader's target (0.80-0.95; default 0.90): higher means more reviews.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

DEFAULT_RETENTION = 0.90
MIN_RETENTION, MAX_RETENTION = 0.80, 0.95
FSRS_STATE_KEY = "fsrs"


def clamp_retention(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError("desired_retention must be a number") from None
    if not MIN_RETENTION <= v <= MAX_RETENTION:
        raise ValueError(f"desired_retention must be between {MIN_RETENTION} and {MAX_RETENTION}")
    return round(v, 2)


def _parse_time(value: Any) -> Optional[datetime.datetime]:
    if isinstance(value, datetime.datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


class FsrsScheduler:
    def __init__(self, desired_retention: float = DEFAULT_RETENTION):
        from fsrs import Scheduler

        self._scheduler = Scheduler(desired_retention=clamp_retention(desired_retention),
                                    learning_steps=(), relearning_steps=(), enable_fuzzing=False)

    @staticmethod
    def _rating(outcome: str):
        from fsrs import Rating

        return Rating.Good if outcome == "remembered" else Rating.Again

    def card_for(self, item: Dict[str, Any], attempts: Iterable[Dict[str, Any]]):
        """The item's FSRS card: stored state, or rebuilt from its attempt history."""
        from fsrs import Card

        state = (item.get("metadata") or {}).get(FSRS_STATE_KEY)
        if isinstance(state, dict):
            try:
                return Card.from_dict(state)
            except Exception:
                pass  # unreadable state -> rebuild from history below
        created = _parse_time(item.get("created_at")) or datetime.datetime.now(datetime.timezone.utc)
        card = Card(due=created)
        history = sorted(
            (a for a in attempts if _parse_time(a.get("reviewed_at") or a.get("created_at"))),
            key=lambda a: _parse_time(a.get("reviewed_at") or a.get("created_at")),
        )
        for a in history:
            card, _ = self._scheduler.review_card(card, self._rating(str(a.get("outcome") or "")),
                                                  _parse_time(a.get("reviewed_at") or a.get("created_at")))
        return card

    def review(self, item: Dict[str, Any], attempts: Iterable[Dict[str, Any]], outcome: str,
               when: datetime.datetime) -> Tuple[Dict[str, Any], datetime.datetime, int]:
        """Applies one review. Returns (state to store, next due time, interval in whole days)."""
        card = self.card_for(item, attempts)
        card, _ = self._scheduler.review_card(card, self._rating(outcome), when)
        due = card.due if card.due.tzinfo else card.due.replace(tzinfo=datetime.timezone.utc)
        days = max(1, round((due - when).total_seconds() / 86400))
        return card.to_dict(), due, days
