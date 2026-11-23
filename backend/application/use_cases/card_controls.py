"""
Faz 5 — the reader's control over their review cards, the retention setting and Anki export.

- edit: only question / answer / explanation / title / concept / status can change (the old PATCH
  accepted any column, e.g. a reader could rewrite their own schedule or counters);
- regenerate: one new AI question for a card (one LLM call, at most 5 per card), keeping the last
  questions in metadata so a better earlier one is not lost;
- report a bad question with a reason: the card leaves the queue (archived) and the reason is kept;
- learning settings: FSRS target retention (stored per reader; used when FSRS_ENABLED);
- export: every card as an Anki package (.apkg) with stable note ids, so re-importing updates
  instead of duplicating.
"""

from __future__ import annotations

import datetime
import html
import io
import os
import sqlite3
import tempfile
import zipfile
from typing import Any, Dict, List, Optional

from .fsrs_scheduling import DEFAULT_RETENTION, clamp_retention

EDITABLE_FIELDS = {"question": 500, "answer": 5000, "explanation": 2000, "title": 200, "concept": 120}
EDITABLE_STATUSES = {"active", "paused", "archived"}
REPORT_REASONS = ("unclear", "wrong", "too_easy", "duplicate", "other")
MAX_REGENERATIONS = 5
MAX_EXPORT_CARDS = 5000


def clean_item_updates(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict) or not data:
        raise ValueError("nothing to update")
    unknown = set(data) - set(EDITABLE_FIELDS) - {"status"}
    if unknown:
        raise ValueError("these fields cannot be edited: " + ", ".join(sorted(unknown)))
    out: Dict[str, Any] = {}
    for field, limit in EDITABLE_FIELDS.items():
        if field in data:
            value = data[field]
            if not isinstance(value, str):
                raise ValueError(f"{field} must be text")
            value = value.strip()
            if field in ("question", "answer", "title", "concept") and not value:
                raise ValueError(f"{field} cannot be empty")
            if len(value) > limit:
                raise ValueError(f"{field} is longer than {limit} characters")
            out[field] = value
    if "status" in data:
        if data["status"] not in EDITABLE_STATUSES:
            raise ValueError("status must be active, paused or archived")
        out["status"] = data["status"]
    return out


class CardControlsUseCase:
    def __init__(self, learning_repo, review_queue_uc=None, settings_repo=None, fsrs_enabled: bool = False):
        self._repo = learning_repo
        self._queue = review_queue_uc
        self._settings = settings_repo
        self._fsrs_enabled = fsrs_enabled

    def _item(self, user_id: str, item_id: str) -> Dict[str, Any]:
        item = self._repo.get_review_item_by_id(item_id, user_id)
        if not item:
            raise LookupError("review item not found")
        return item

    def edit(self, user_id: str, item_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        updates = clean_item_updates(data)
        self._item(user_id, item_id)
        return self._repo.update_review_item(item_id, user_id, updates)

    def regenerate(self, user_id: str, item_id: str) -> Dict[str, Any]:
        item = self._item(user_id, item_id)
        meta = dict(item.get("metadata") or {})
        count = int(meta.get("regenerations") or 0)
        if count >= MAX_REGENERATIONS:
            raise PermissionError("this card was regenerated too often; edit it instead")
        if not self._queue or not getattr(self._queue, "_llm_port", None):
            raise RuntimeError("question generation is not available")
        answer = str(item.get("answer") or "")
        question = self._queue._recall_question(answer, str(item.get("concept") or "this book"), [1])
        if not question or question.startswith("What is the key takeaway from") or question == item.get("question"):
            raise RuntimeError("no better question could be generated right now")
        meta["regenerations"] = count + 1
        meta["previous_questions"] = ([item.get("question")] + list(meta.get("previous_questions") or []))[:3]
        return self._repo.update_review_item(item_id, user_id, {"question": question, "metadata": meta})

    def report(self, user_id: str, item_id: str, reason: str, comment: str = "") -> Dict[str, Any]:
        if reason not in REPORT_REASONS:
            raise ValueError("reason must be one of " + ", ".join(REPORT_REASONS))
        item = self._item(user_id, item_id)
        meta = dict(item.get("metadata") or {})
        meta["report"] = {"reason": reason, "comment": str(comment or "").strip()[:300],
                          "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        return self._repo.update_review_item(item_id, user_id, {"status": "archived", "metadata": meta})

    # ── Settings ────────────────────────────────────────────────────────────
    def get_settings(self, user_id: str, token: Optional[str]) -> Dict[str, Any]:
        stored = self._settings.get(user_id, token) if self._settings else None
        return {"fsrs_enabled": self._fsrs_enabled,
                "desired_retention": float((stored or {}).get("desired_retention") or DEFAULT_RETENTION)}

    def save_settings(self, user_id: str, token: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._settings:
            raise RuntimeError("settings are not available")
        retention = clamp_retention((data or {}).get("desired_retention"))
        self._settings.upsert(user_id, token, {"desired_retention": retention})
        return {"fsrs_enabled": self._fsrs_enabled, "desired_retention": retention}

    def retention_for(self, user_id: str, token: Optional[str]) -> float:
        try:
            return self.get_settings(user_id, token)["desired_retention"]
        except Exception:
            return DEFAULT_RETENTION

    # ── Anki export ─────────────────────────────────────────────────────────
    def export_anki(self, user_id: str) -> bytes:
        items: List[Dict[str, Any]] = []
        for status in ("active", "paused"):
            items += self._repo.list_review_items(user_id=user_id, status=status, limit=MAX_EXPORT_CARDS) or []
        return build_apkg(items[:MAX_EXPORT_CARDS])


ANKI_MODEL_ID = 1607392319   # fixed ids: re-importing updates the same note type and deck
ANKI_DECK_ID = 2059400110


def build_apkg(items: List[Dict[str, Any]], timestamp: Optional[float] = None) -> bytes:
    import genanki

    model = genanki.Model(
        ANKI_MODEL_ID, "Libris card",
        fields=[{"name": "Question"}, {"name": "Answer"}, {"name": "Book"}, {"name": "LibrisId"}],
        templates=[{"name": "Recall", "qfmt": "{{Question}}<div class=book>{{Book}}</div>",
                    "afmt": "{{FrontSide}}<hr id=answer>{{Answer}}"}],
        css=".card{font-family:Georgia,serif;font-size:20px;text-align:left;max-width:640px;margin:auto}"
            ".book{margin-top:1em;font-size:14px;color:#777}",
    )
    deck = genanki.Deck(ANKI_DECK_ID, "Libris")
    for item in items:
        def esc(v):
            return html.escape(str(v or "")).replace("\n", "<br>")
        deck.add_note(genanki.Note(
            model=model,
            fields=[esc(item.get("question")), esc(item.get("answer")), esc(item.get("concept")), str(item.get("id") or "")],
            guid=genanki.guid_for("libris", str(item.get("id") or item.get("question"))),
        ))
    package = genanki.Package(deck)
    # genanki.Package.write_to_file leaves its SQLite temp file (with the reader's cards) on disk;
    # build the same archive with our own temp file and always delete it.
    fd, path = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        try:
            ts = timestamp if timestamp is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
            id_gen = iter(range(int(ts * 1000), int(ts * 1000) + 10_000_000))
            package.write_to_db(conn.cursor(), ts, id_gen)
            conn.commit()
        finally:
            conn.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(path, "collection.anki2")
            z.writestr("media", "{}")
        return buf.getvalue()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
