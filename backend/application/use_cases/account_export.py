"""
Full personal-data export (KVKK / GDPR data portability): everything Libris stores about the
signed-in reader, as JSON (machine-readable) or Markdown (human-readable).

Each section is read independently. If one source fails (for example a table that does not exist
in this database yet), the export still contains every other section and lists the missing one
under `unavailable_sections`, instead of failing or silently returning less.
"""

import datetime
import json
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
PAGE = 100
MAX_ROWS = 20_000  # per section; far above any real reader, guards against a runaway loop


def _paged(fetch: Callable[[int, int], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    while len(rows) < MAX_ROWS:
        page = fetch(PAGE, len(rows)) or []
        rows.extend(page)
        if len(page) < PAGE:
            break
    return rows


class ExportAccountDataUseCase:
    def __init__(self, interaction_repo, note_repo=None, note_review_repo=None, learning_repo=None):
        self._interactions = interaction_repo
        self._notes = note_repo
        self._note_reviews = note_review_repo
        self._learning = learning_repo

    def collect(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise PermissionError("authentication required")
        data: Dict[str, Any] = {
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "user_id": user_id,
        }
        unavailable: List[str] = []

        def section(name: str, read: Callable[[], Any], empty: Any) -> None:
            try:
                data[name] = read()
            except Exception as exc:
                logger.warning("Export section %s unavailable: %s", name, type(exc).__name__)
                data[name] = empty
                unavailable.append(name)

        section("profile", lambda: self._interactions.get_user_profile(user_id), None)
        section("library", lambda: self._interactions.get_user_interactions(user_id), [])
        section("favorites", lambda: self._interactions.get_user_favorites(user_id), [])
        if self._notes is not None:
            section("notes", lambda: _paged(lambda lim, off: self._notes.get_user_notes(user_id, limit=lim, offset=off)), [])
        if self._note_reviews is not None and data.get("notes"):
            def reviews():
                out = []
                for note in data["notes"]:
                    review = self._note_reviews.get_review_by_note_id(str(note.get("id")), user_id)
                    if review:
                        out.append(review)
                return out
            section("note_reviews", reviews, [])
        if self._learning is not None:
            section("review_cards", lambda: _paged(
                lambda lim, off: self._learning.list_review_items(user_id, status=None, limit=lim, offset=off)), [])
            section("review_history", lambda: _paged(
                lambda lim, off: self._learning.get_review_attempts(user_id, limit=lim, offset=off)), [])
        data["unavailable_sections"] = unavailable
        return data

    def execute(self, user_id: str, export_format: str = "json") -> Dict[str, str]:
        fmt = (export_format or "json").strip().lower()
        if fmt not in ("json", "markdown", "md"):
            raise ValueError("format must be json or markdown")
        data = self.collect(user_id)
        stamp = data["exported_at"][:10]
        if fmt == "json":
            return {"content": json.dumps(data, ensure_ascii=False, indent=2, default=str),
                    "mime_type": "application/json; charset=utf-8", "filename": f"libris-export-{stamp}.json"}
        return {"content": render_markdown(data), "mime_type": "text/markdown; charset=utf-8",
                "filename": f"libris-export-{stamp}.md"}


def _line(value: Any) -> str:
    return str(value if value is not None else "").replace("\r", " ").strip()


def render_markdown(data: Dict[str, Any]) -> str:
    out = ["# Libris: my data", "", f"Exported: {data['exported_at']}", ""]
    if data.get("unavailable_sections"):
        out += [f"> Not available in this export: {', '.join(data['unavailable_sections'])}", ""]
    notes = data.get("notes") or []
    out += [f"## Notes ({len(notes)})", ""]
    by_book: Dict[str, List[Dict[str, Any]]] = {}
    for n in notes:
        by_book.setdefault(_line(n.get("book_id")) or "-", []).append(n)
    for book, items in by_book.items():
        out += [f"### {book}", ""]
        for n in items:
            out += [f"- **{_line(n.get('note_type'))}** ({_line(n.get('created_at'))[:10]}): {_line(n.get('content'))}"]
        out.append("")
    cards = data.get("review_cards") or []
    out += [f"## Review cards ({len(cards)})", ""]
    for c in cards:
        out += [f"- **Q:** {_line(c.get('question'))}", f"  **A:** {_line(c.get('answer'))}"]
    out.append("")
    history = data.get("review_history") or []
    out += [f"## Review history ({len(history)} attempts)", ""]
    for a in history:
        out += [f"- {_line(a.get('reviewed_at'))[:19]}: {_line(a.get('outcome'))}"]
    out.append("")
    library = data.get("library") or []
    out += [f"## Library ({len(library)})", ""]
    for item in library:
        out += [f"- {_line(item.get('book_id'))}: {_line(item.get('interaction_type'))}"]
    favorites = data.get("favorites") or []
    out += ["", f"## Favourites ({len(favorites)})", ""]
    for f in favorites:
        out += [f"- {_line(f.get('book_title') or f.get('book_id'))}"]
    out += ["", "## Profile", "", "```json", json.dumps(data.get("profile"), ensure_ascii=False, indent=2, default=str), "```", ""]
    return "\n".join(out)
