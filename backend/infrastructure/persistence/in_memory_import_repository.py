"""In-process import queue for local development and tests (same contract as SupabaseImportRepository;
the database version adds RLS, the per-reader unique hash and the 5000-entry cap trigger)."""

import datetime
import threading
import uuid
from typing import Any, Dict, List, Optional


class InMemoryImportRepository:
    def __init__(self):
        self._rows: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _mine(self, user_id: str):
        return [r for r in self._rows.values() if r["user_id"] == user_id]

    def count_pending(self, user_id: str, user_token: Optional[str]) -> int:
        return sum(1 for r in self._mine(user_id) if r["status"] == "pending")

    def insert_pending(self, user_id: str, user_token: Optional[str], rows: List[Dict[str, Any]]) -> int:
        inserted = 0
        with self._lock:
            hashes = {r["content_hash"] for r in self._mine(user_id)}
            for row in rows:
                if row["content_hash"] in hashes:
                    continue
                rid = str(uuid.uuid4())
                self._rows[rid] = {**row, "id": rid, "user_id": user_id, "status": "pending", "note_id": None,
                                   "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                hashes.add(row["content_hash"])
                inserted += 1
        return inserted

    def list_pending(self, user_id: str, user_token: Optional[str], limit: int):
        rows = [r for r in self._mine(user_id) if r["status"] == "pending"]
        return sorted(rows, key=lambda r: (r["book_title"], r["created_at"]))[:limit]

    def get_pending(self, user_id: str, user_token: Optional[str], ids):
        return [r for r in self._mine(user_id) if r["id"] in set(ids) and r["status"] == "pending"]

    def set_status(self, user_id: str, user_token: Optional[str], ids, status: str) -> int:
        n = 0
        for r in self._mine(user_id):
            if r["id"] in set(ids) and r["status"] == "pending":
                r["status"] = status
                n += 1
        return n

    def mark_approved(self, user_id: str, user_token: Optional[str], item_id: str, note_id, book_id: str) -> None:
        row = self._rows.get(item_id)
        if row and row["user_id"] == user_id:
            row.update(status="approved", note_id=note_id, book_id=book_id)
