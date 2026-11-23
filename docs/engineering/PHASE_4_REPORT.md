# Faz 4 — Imports (report)

Branch `feat/phase-4-imports` (stacked on `feat/phase-3-reminders`). Goal: a new reader brings years
of highlights in with one file instead of starting from zero — without polluting the library or
burning the AI budget.

## What changed

| Area | Change |
| --- | --- |
| Parsers | Kindle `My Clippings.txt` (highlights, notes; bookmarks and Kindle's "clipping limit" placeholders skipped; English/German/French/Spanish/Italian/Turkish/Dutch/Portuguese labels; BOM and CRLF), Readwise CSV (multi-line quoted highlights, the Note column as a separate note), Goodreads CSV (exclusive shelf → want to read / reading / finished, `="978…"` ISBN13, rating, My Review as a note). Wrong files get a clear message ("doesn't look like a Goodreads export"). |
| Dedup | SHA-256 of kind + normalised title + normalised text — **source-independent**, so a highlight imported from Kindle and later from Readwise is stored once. Unique per reader in the database. Approved notes also carry `client_id = import:<hash>` (existing unique index). Dismissed entries stay as `rejected`, so they don't come back on the next import. |
| Matching | One catalogue lookup per distinct book (max 300 per import); ISBN13 first (Goodreads), else normalised title (subtitle, series, articles, accents removed) + at least one shared author word. Deliberately conservative: a partial title never matches; the reader picks the book for unmatched groups. |
| Approval queue | Migration **19** `import_items` (RLS own rows, shape checks, 5000-pending cap enforced by a trigger, cascade on account deletion; rollback script). API: `POST /api/imports`, `GET /api/imports/pending`, `POST /api/imports/decide` (approve / reject, ≤100 ids per call, book overrides). Highlights become review cards (default) or plain notes; Kindle/Readwise notes and Goodreads reviews become personal notes; shelves go to the library through the existing feedback use case. |
| AI budget | Approving any number of entries makes **at most 5 LLM calls** per request (the existing `MAX_RECALL_QUESTIONS_PER_REQUEST`). The rest are not given a generic card any more: they wait and get real questions 5 at a time on the next review-queue loads. (Before: every note beyond the 5th got "What is the key takeaway from X?" permanently.) Without an LLM, or on provider errors, the old fallback still applies. |
| Limits | File ≤ 4 MB; the browser sends it in pieces < 1 MB cut only between entries (Kindle separator / CSV record boundary, header repeated) — the server-action limit stays at 1 MB for the whole app. `/api/imports` alone accepts up to 6 MB per request; everything else keeps the 1 MB cap. ≤ 3000 entries per piece, 5000 pending per reader. |
| Web | `/import`: source cards with "where to find the file" help, auto-detection of the source, progress for multi-piece files, summary (new / already known / skipped / books matched), queue grouped by book with select-all, catalogue picker for unmatched books, "Highlights become: Review cards / Notes only", approve/dismiss. Entry points on My Library (header + empty state). |
| Share target | `manifest.share_target` (POST, multipart): sharing a clippings/CSV file or a quote from another app to the installed Libris opens `/import`. The service worker parks the payload in Cache Storage (origin-only, ≤ 4 MB) and the page takes it once; a shared quote can be saved as a review card after picking the book. |
| Also | Untranslated "Try adjusting your search terms…" on My Library replaced with a translated hint. 51 new strings in 6 languages. |

## How it was tested

- `backend/tests/test_imports.py` (19): every parser incl. BOM/CRLF, German Kindle, multi-line quoted CSV, Goodreads ISBN/rating/shelves; wrong/empty files; hash equality across sources; title normalisation and conservative matching; dedup within a file and across imports; full queue message; approval → notes, needs-book list, overrides, LLM budget ≤ 5 with the rest deferred, Kindle notes as personal notes; Goodreads shelves to the library; dismissed entries never return; id validation; endpoints need login; `/api/imports` accepts > 1 MB but ≤ 6 MB while `/api/notes` keeps 413 (mutation-checked: removing the per-route limit fails the test).
- `test_recall_question_generation.py`: budget test updated to the new rule (5 calls, no generic cards, next request converts the rest) + batch conversion test.
- `backend/tests/sql/test_19_import_queue.sql` on real PostgreSQL (locally and in CI): dedup constraint, shape checks, hash format, RLS between readers, write-as-other refused, 5000 cap with direct inserts, anon denied, cascade; migration applied twice, rolled back, re-applied.
- Web unit (5 new): Kindle/CSV splitting never tears an entry or a quoted field and loses nothing; BOM/CRLF; source detection; page/SW/manifest wiring.
- Offline signed-in journey: Library → Import → Kindle file (BOM, CRLF, bookmark, note, unmatched book) → summary "3 new from 2 books (1 matched), 1 skipped" → re-import adds 0 → pick the book for the unmatched group → approve → "3 added. 2 review questions are ready." → queue empty; no page errors.
- Gates: ruff clean, backend 1273 passed, web lint/types clean, unit 284/284, build OK, e2e (see PR).

## Manual production steps (owner)

1. Apply `19_import_queue.sql` (after 09/10/13; independent of 17/18). Rollback: `scripts/rollbacks/19_import_queue_rollback.sql`.
2. Nothing else: no new secrets, no paid service. The share target works once Libris is installed as an app (Android/desktop Chrome; iOS Safari does not support Web Share Target).

## Rollback

Revert the PR; run the rollback script (approved notes/shelves are normal data and remain).

## Known limits

- Kindle PDFs/personal documents without a catalogue match need a manual book pick per book group (by design; no auto-creation of catalogue entries).
- iOS Safari has no Web Share Target; iPhone readers upload the file on the page instead.

## Correction (found after this report was first written)

The CI e2e failure seen on #99, #101 and Dependabot branches was first noted as "flaky". It was a
real bug on `main`: the AI catalog lookup added columns to the catalog frame shared by all request
threads; two simultaneous first chats corrupted it, and chat plus every recommendation failed until
restart. Reproduced (both CI messages), fixed in `ai_rag.py` with a side cache, regression test
`test_shared_catalog_thread_safety.py` (fails 3/3 on the old code). The same change makes books
contributed after the first chat findable in chat.

`test_18_push_and_events.sql` also failed once: `now()` is constant inside a transaction, so the
"newest device" was random. `push_subscribe` now uses `clock_timestamp()` and never drops the device
just added (200/200 rounds locally).
