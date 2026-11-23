# Faz 5 — Card control, FSRS, Anki (report)

Branch `feat/phase-5-card-control` (contains Faz 3 and Faz 4).

## What changed

| Area | Change |
| --- | --- |
| Card controls | "⋯" menu on every review card: **edit**, **new AI question** (one LLM call, at most 5 per card, the last 3 questions are kept in metadata), **report a bad question** with a reason (unclear / wrong / too easy / duplicate / other) and an optional comment. A reported card is archived; the note stays. |
| Security fix | `PUT/PATCH /api/learning/items/<id>` passed the raw body to the database (a reader could write their own `stage`, `next_review_at`, counters). It now accepts only question, answer, explanation, title, concept and status, with length limits. |
| Bug fix | The review queue only looked at *active* cards when deciding whether a note already has one, so a reported or paused card came back as a new card on the next load. Cards of every status count now (mutation-checked test). |
| FSRS | `fsrs==6.3.0` behind `FSRS_ENABLED` (default **off**; the fixed 1/3/7/14/30-day policy is unchanged). remembered → Good, struggled → Again; whole-day intervals, no fuzzing. Card state lives in `review_items.metadata.fsrs`; a card without state is rebuilt from its `review_attempts`, so switching the flag on does not reset progress. Any FSRS error falls back to the old policy. |
| Retention target | Migration **20** `learning_settings` (RLS, 0.80–0.95, cascade, rollback). Slider in Settings, shown only when FSRS is on. |
| Anki export | `GET /api/learning/export/anki` → `.apkg` with stable ids (re-import updates instead of duplicating), HTML-escaped. genanki's own writer leaves a temporary SQLite file with the reader's cards on disk; we write the archive ourselves and always delete it. |
| UI | Review tabs no longer wrap or get cut off on phones and have tab roles; imported cards name their book. |
| Strings | 27 new keys in 6 languages. |

## How it was tested

- `test_card_controls_fsrs_anki.py` (13), `test_20_learning_settings.sql` on real PostgreSQL (locally; CI runs it too), web unit tests.
- Gates on this branch: ruff clean, backend **1288 passed** (10 skipped), web unit **286/286**, e2e **87 passed** (3 skipped, same as before).
- Offline signed-in journey, desktop and phone, 11 checks each: menu by mouse and keyboard, edit, regenerate without an LLM, report, stays away after reload, retention saved and persisted, `.apkg` download.

**Not tested:** a successful "new AI question" against the real Gemini API (the harness has no key; the unit tests use a stub), importing the file into the Anki app itself (the package was opened as SQLite instead), and FSRS on real readers' history.

## Manual production steps (owner)

1. Apply `20_learning_settings.sql` (rollback in `scripts/rollbacks/`).
2. Optional: set `FSRS_ENABLED=true` on Render. Without it nothing about scheduling changes.

## Rollback

Unset `FSRS_ENABLED` (cards continue on the old policy from their `stage`), revert the PR, run the rollback script.

## Dependencies

`genanki` (MIT) brings `frozendict` (LGPL-3.0, used unmodified as a library), `chevron`, `pyyaml`, `cached-property`.

## Test that was changed, not only added

`test_recall_question_generation.py::test_llm_calls_are_bounded_per_request…` (Faz 4) used to expect a generic card for every note beyond the 5-call budget. The product rule changed (those notes wait for a real question), so the expectation changed with it; the 5-call limit is still asserted.
