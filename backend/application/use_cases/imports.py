"""
Faz 4 — imports: Kindle "My Clippings.txt", Readwise CSV and Goodreads CSV.

Flow: the file's text is parsed here (pure functions), every entry gets a content hash, books are
matched against the catalogue, and the entries land in the reader's approval queue
(`import_items`, status pending). Nothing reaches the notes or the library until the reader
approves it. Hashes are source-independent, so the same highlight imported from Kindle and later
from Readwise is stored once, and a rejected entry does not come back on the next import.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SOURCES = ("kindle", "readwise", "goodreads")
MAX_IMPORT_CHARS = 4_000_000          # ~4 MB of text per import request
MAX_ITEMS_PER_IMPORT = 3000
MAX_PENDING_PER_USER = 5000           # also enforced by a trigger in migration 19
MAX_BOOKS_TO_MATCH = 300              # distinct books looked up in the catalogue per import
MAX_CONTENT_CHARS = 5000              # same limit as a note
MAX_APPROVE_PER_REQUEST = 100
GOODREADS_SHELVES = {"read": "finished", "currently-reading": "reading", "to-read": "want_to_read"}


@dataclass
class ParsedItem:
    kind: str                        # highlight | note | shelf
    book_title: str
    book_author: str = ""
    content: str = ""
    location: str = ""
    isbn13: str = ""
    shelf: str = ""
    rating: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    items: List[ParsedItem]
    skipped: int = 0                 # bookmarks, empty or unreadable entries
    truncated: int = 0               # entries over MAX_ITEMS_PER_IMPORT


# ── Normalisation and hashing ────────────────────────────────────────────────

def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def normalize_title(title: str) -> str:
    t = _fold(title)
    t = re.sub(r"\s*[\(\[].*?[\)\]]\s*", " ", t)      # (Series #2), [Kindle Edition]
    t = re.split(r"\s*[:–—]\s+|\s+-\s+", t)[0]  # subtitle
    t = re.sub(r"^(the|a|an|der|die|das|le|la|les|el|los|il|lo)\s+", "", t)
    return re.sub(r"[^\w ]+", "", t).strip()


def author_tokens(author: str) -> set:
    return {w for w in re.findall(r"[a-z]{3,}", _fold(author))}


def content_hash(item: ParsedItem) -> str:
    if item.kind == "shelf":
        key = f"shelf|{item.isbn13 or normalize_title(item.book_title) + '|' + _fold(item.book_author)}"
    else:
        key = f"{item.kind}|{normalize_title(item.book_title)}|{_fold(item.content)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ── Kindle "My Clippings.txt" ────────────────────────────────────────────────

_KINDLE_SEPARATOR = re.compile(r"^={5,}\s*$", re.M)
_KINDLE_HIGHLIGHT = re.compile(r"highlight|markierung|surlignement|subrayado|evidenziazione|vurgu|markering|destaque", re.I)
_KINDLE_NOTE = re.compile(r"\bnote\b|notiz|\bnota\b|\bnot\b|notitie", re.I)
_KINDLE_BOOKMARK = re.compile(r"bookmark|lesezeichen|signet|marcador|segnalibro|yer i[sş]areti|bladwijzer", re.I)
_KINDLE_LOCATION = re.compile(r"(?:location|position|emplacement|posici[oó]n|posizione|konum|locatie)\s*([\d\-–]+)", re.I)
_KINDLE_LIMIT = re.compile(r"^\s*<\s*you have reached the clipping limit", re.I)
_KINDLE_PAGE = re.compile(r"(?:page|seite|p[aá]gina|sayfa|pagina)\s*([\divxlc\-–]+)", re.I)


def _kindle_title_author(line: str) -> Tuple[str, str]:
    line = line.lstrip("﻿").strip()
    m = re.match(r"^(.*)\(([^()]*)\)\s*$", line)
    if m and m.group(1).strip():
        return m.group(1).strip(), m.group(2).strip()
    return line, ""


def parse_kindle(text: str) -> ParseResult:
    result = ParseResult(items=[])
    for block in _KINDLE_SEPARATOR.split(text.replace("\r\n", "\n").replace("\r", "\n")):
        lines = block.strip("\n").split("\n")
        if len(lines) < 2 or not lines[0].strip():
            if block.strip():
                result.skipped += 1
            continue
        title, author = _kindle_title_author(lines[0])
        meta = lines[1].strip()
        body = "\n".join(lines[2:]).strip()
        if _KINDLE_BOOKMARK.search(meta) or not body or _KINDLE_LIMIT.match(body):
            result.skipped += 1
            continue
        kind = "note" if (_KINDLE_NOTE.search(meta) and not _KINDLE_HIGHLIGHT.search(meta)) else "highlight"
        loc = _KINDLE_LOCATION.search(meta) or _KINDLE_PAGE.search(meta)
        result.items.append(ParsedItem(kind=kind, book_title=title, book_author=author, content=body,
                                       location=(loc.group(0) if loc else "")[:120]))
    return result


# ── CSV helpers ──────────────────────────────────────────────────────────────

def _csv_rows(text: str) -> List[Dict[str, str]]:
    text = text.lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("the CSV file has no header row")
    reader.fieldnames = [(f or "").strip().lower() for f in reader.fieldnames]
    return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]


def parse_readwise(text: str) -> ParseResult:
    rows = _csv_rows(text)
    if rows and "highlight" not in rows[0]:
        raise ValueError("this does not look like a Readwise export (no 'Highlight' column)")
    result = ParseResult(items=[])
    for row in rows:
        title, highlight = row.get("book title", ""), row.get("highlight", "")
        if not title or not highlight:
            result.skipped += 1
            continue
        loc = row.get("location", "")
        loc_type = row.get("location type", "")
        location = f"{loc_type} {loc}".strip()[:120]
        author = row.get("book author", "")
        result.items.append(ParsedItem("highlight", title, author, highlight, location))
        if row.get("note"):
            result.items.append(ParsedItem("note", title, author, row["note"], location))
    return result


_ISBN_CLEAN = re.compile(r"[^0-9Xx]")


def parse_goodreads(text: str) -> ParseResult:
    rows = _csv_rows(text)
    if rows and "exclusive shelf" not in rows[0]:
        raise ValueError("this does not look like a Goodreads export (no 'Exclusive Shelf' column)")
    result = ParseResult(items=[])
    for row in rows:
        title, shelf = row.get("title", ""), GOODREADS_SHELVES.get(row.get("exclusive shelf", ""))
        if not title or not shelf:
            result.skipped += 1
            continue
        isbn13 = _ISBN_CLEAN.sub("", row.get("isbn13", ""))  # exported as ="9780..."
        try:
            rating = int(row.get("my rating") or 0) or None
        except ValueError:
            rating = None
        result.items.append(ParsedItem("shelf", title, row.get("author", ""), isbn13=isbn13 if len(isbn13) == 13 else "",
                                       shelf=shelf, rating=rating if rating and 1 <= rating <= 5 else None))
        review = row.get("my review", "")
        if review:
            result.items.append(ParsedItem("note", title, row.get("author", ""), review))
    return result


PARSERS: Dict[str, Callable[[str], ParseResult]] = {"kindle": parse_kindle, "readwise": parse_readwise, "goodreads": parse_goodreads}


def parse(source: str, text: str) -> ParseResult:
    if source not in PARSERS:
        raise ValueError("source must be one of " + ", ".join(SOURCES))
    if not isinstance(text, str) or not text.strip():
        raise ValueError("the file is empty")
    if len(text) > MAX_IMPORT_CHARS:
        raise ValueError(f"the file is too large (max {MAX_IMPORT_CHARS // 1_000_000} MB of text)")
    try:
        result = PARSERS[source](text)
    except csv.Error:
        raise ValueError("the CSV file could not be read") from None
    if len(result.items) > MAX_ITEMS_PER_IMPORT:
        result.truncated = len(result.items) - MAX_ITEMS_PER_IMPORT
        result.items = result.items[:MAX_ITEMS_PER_IMPORT]
    return result


# ── Matching against the catalogue ───────────────────────────────────────────

def best_match(title: str, author: str, candidates: Iterable[Dict[str, Any]]) -> Optional[str]:
    """isbn13 of the catalogue book with the same normalised title and (when both sides name an
    author) at least one shared author word. Conservative on purpose: a wrong match would attach
    highlights to the wrong book; the reader can still pick the book by hand."""
    want_title, want_authors = normalize_title(title), author_tokens(author)
    for book in candidates:
        if normalize_title(book.get("title") or "") != want_title or not want_title:
            continue
        have = author_tokens(str(book.get("authors") or ""))
        if want_authors and have and not (want_authors & have):
            continue
        isbn = str(book.get("isbn13") or "").strip()
        if isbn:
            return isbn
    return None


class ImportUseCase:
    """Parse → match → queue; approve / reject. Repositories act with the reader's own JWT."""

    def __init__(self, repo, catalog, create_note_uc, review_queue_uc=None, feedback_uc=None, book_data_port=None):
        self._repo = repo
        self._catalog = catalog
        self._create_note = create_note_uc
        self._review_queue = review_queue_uc
        self._feedback = feedback_uc
        self._books = book_data_port

    def _match_books(self, items: List[ParsedItem]) -> Tuple[Dict[Tuple[str, str], Optional[str]], int]:
        keys: Dict[Tuple[str, str], Optional[str]] = {}
        isbns = {i.isbn13 for i in items if i.isbn13}
        known_isbns = set()
        if isbns and self._books:
            try:
                known_isbns = {str(b.get("isbn13")) for b in self._books.get_books_by_isbns(sorted(isbns)) or []}
            except Exception:
                known_isbns = set()
        looked_up = 0
        for it in items:
            key = (normalize_title(it.book_title), _fold(it.book_author))
            if key in keys:
                continue
            if it.isbn13 and it.isbn13 in known_isbns:
                keys[key] = it.isbn13
                continue
            if looked_up >= MAX_BOOKS_TO_MATCH or not self._catalog:
                keys[key] = None
                continue
            looked_up += 1
            try:
                query = re.split(r"\s*[:(\[]", it.book_title)[0][:120]
                keys[key] = best_match(it.book_title, it.book_author, self._catalog.search_books(query=query, limit=10) or [])
            except Exception:
                keys[key] = None
        return keys, looked_up

    def import_text(self, user_id: str, token: str, source: str, text: str) -> Dict[str, Any]:
        parsed = parse(source, text)
        pending = self._repo.count_pending(user_id, token)
        room = max(0, MAX_PENDING_PER_USER - pending)
        if room == 0:
            raise ValueError("your import queue is full: approve or dismiss some entries first")
        matches, _ = self._match_books(parsed.items)
        rows, seen = [], set()
        for it in parsed.items:
            h = content_hash(it)
            if h in seen:
                continue
            seen.add(h)
            rows.append({
                "source": source, "kind": it.kind, "content_hash": h,
                "book_title": it.book_title[:500], "book_author": (it.book_author or "")[:300] or None,
                "book_id": matches.get((normalize_title(it.book_title), _fold(it.book_author))),
                "content": it.content[:MAX_CONTENT_CHARS] if it.content else None,
                "location": it.location[:120] or None, "shelf": it.shelf or None, "rating": it.rating,
            })
        in_file_duplicates = len(parsed.items) - len(rows)
        over_room = max(0, len(rows) - room)
        rows = rows[:room]
        inserted = self._repo.insert_pending(user_id, token, rows) if rows else 0
        books = {(r["book_title"], r["book_author"]) for r in rows}
        matched = {(r["book_title"], r["book_author"]) for r in rows if r["book_id"]}
        return {
            "parsed": len(parsed.items), "new": inserted,
            "duplicates": in_file_duplicates + (len(rows) - inserted),
            "skipped": parsed.skipped, "truncated": parsed.truncated + over_room,
            "books": len(books), "books_matched": len(matched),
        }

    def list_pending(self, user_id: str, token: str, limit: int = 200) -> Dict[str, Any]:
        items = self._repo.list_pending(user_id, token, min(max(1, limit), 500))
        return {"items": items, "pending": self._repo.count_pending(user_id, token)}

    def reject(self, user_id: str, token: str, ids: List[str]) -> int:
        return self._repo.set_status(user_id, token, _clean_ids(ids), "rejected")

    def approve(self, user_id: str, token: str, ids: List[str], highlight_as: str = "key_takeaway",
                book_overrides: Optional[Dict[str, str]] = None, generate_questions: bool = True) -> Dict[str, Any]:
        if highlight_as not in ("key_takeaway", "personal_note"):
            raise ValueError("highlight_as must be key_takeaway or personal_note")
        overrides = {str(k): str(v).strip()[:64] for k, v in (book_overrides or {}).items() if str(v).strip()}
        items = self._repo.get_pending(user_id, token, _clean_ids(ids))
        approved, needs_book, failed, notes = [], [], 0, []
        for item in items:
            book_id = overrides.get(str(item["id"])) or item.get("book_id")
            if not book_id:
                needs_book.append(item["id"])
                continue
            try:
                if item["kind"] == "shelf":
                    if not self._feedback:
                        failed += 1
                        continue
                    self._feedback.execute(user_id, book_id, item["shelf"])
                    approved.append((item["id"], None, book_id))
                    continue
                note_type = highlight_as if item["kind"] == "highlight" else "personal_note"
                note = self._create_note.execute(user_id=user_id, book_id=book_id, note_type=note_type,
                                                 content=item["content"], client_id=f"import:{item['content_hash'][:48]}")
                if not (note.get("book") or {}).get("title"):
                    # The card names its book even where the catalogue lookup is unavailable.
                    note = {**note, "book": {"title": item.get("book_title") or ""}}
                notes.append(note)
                approved.append((item["id"], note.get("id"), book_id))
            except Exception:
                failed += 1
        for item_id, note_id, book_id in approved:
            self._repo.mark_approved(user_id, token, item_id, note_id, book_id)
        questions, deferred = 0, 0
        if self._review_queue and notes:
            if generate_questions:
                created, deferred = self._review_queue.create_items_for_notes(user_id, notes)
            else:
                created, deferred = [], sum(1 for n in notes if n.get("note_type") == "key_takeaway")
            questions = len(created)
        return {"approved": len(approved), "needs_book": needs_book, "failed": failed,
                "questions_created": questions, "questions_deferred": deferred}


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _clean_ids(ids: Any) -> List[str]:
    if not isinstance(ids, list) or not ids:
        raise ValueError("ids must be a non-empty list")
    if len(ids) > MAX_APPROVE_PER_REQUEST:
        raise ValueError(f"at most {MAX_APPROVE_PER_REQUEST} entries per request")
    clean = [str(i).lower() for i in ids if isinstance(i, str) and _UUID.match(str(i).lower())]
    if len(clean) != len(ids):
        raise ValueError("ids must be UUIDs")
    return clean
