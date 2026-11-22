"""
Hourly reminder run (Faz 3). Scheduled by .github/workflows/reminders.yml; safe to run by hand.

    python -m backend.scripts.send_reminders            # sends
    python -m backend.scripts.send_reminders --dry-run  # builds the e-mails, sends nothing, writes nothing

Connects as the least-privilege `reminder_worker` role (REMINDER_DB_URL), which can only list
candidates and write the send log. For each candidate it claims (user, local date) in
reminder_sends first, so a second run or a concurrent one never sends twice; if the provider fails
with a retryable error the claim is released and the next hour retries. Logs counts only, never
addresses or question text.

Environment: REMINDER_DB_URL, RESEND_API_KEY, REMINDER_FROM ("Libris <reminders@your-domain>"),
APP_URL (web), API_URL (backend, for the unsubscribe link). Missing settings -> exits 0 with a
notice, so the schedule does not fail before the operator has configured it.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.application.use_cases.reminders import build_reminder_email  # noqa: E402
from backend.infrastructure.email.resend_adapter import (  # noqa: E402
    EmailMessage,
    EmailSendError,
    FakeEmailAdapter,
    ResendEmailAdapter,
)

logger = logging.getLogger("send_reminders")
COLUMNS = ("user_id", "email", "language", "local_date", "unsubscribe_token", "due_count", "first_question")


class PostgresReminderStore:
    """SQL used by the worker; every statement is allowed for the reminder_worker role."""

    def __init__(self, conn):
        self._conn = conn

    def candidates(self, now: datetime.datetime) -> List[Dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM public.reminder_candidates(%s)", (now,))
            return [dict(zip(COLUMNS, row)) for row in cur.fetchall()]

    def claim(self, c: Dict[str, Any]) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.reminder_sends (user_id, local_date, channel, due_count) "
                "VALUES (%s, %s, 'email', %s) ON CONFLICT DO NOTHING RETURNING 1",
                (c["user_id"], c["local_date"], c["due_count"]))
            claimed = cur.fetchone() is not None
        self._conn.commit()
        return claimed

    def release(self, c: Dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM public.reminder_sends WHERE user_id = %s AND local_date = %s AND channel = 'email'",
                        (c["user_id"], c["local_date"]))
        self._conn.commit()


def run(store, email_port, app_url: str, api_url: str, now: Optional[datetime.datetime] = None,
        dry_run: bool = False) -> Dict[str, int]:
    stats = {"candidates": 0, "sent": 0, "skipped": 0, "failed": 0, "permanent_failures": 0}
    for c in store.candidates(now or datetime.datetime.now(datetime.timezone.utc)):
        stats["candidates"] += 1
        mail = build_reminder_email(c, app_url, api_url)
        if dry_run:
            email_port.send(EmailMessage(c["email"], mail.subject, mail.html, mail.text, mail.headers))
            stats["sent"] += 1
            continue
        if not store.claim(c):
            stats["skipped"] += 1  # another run already took this reader today
            continue
        try:
            email_port.send(EmailMessage(c["email"], mail.subject, mail.html, mail.text, mail.headers))
            stats["sent"] += 1
        except EmailSendError as exc:
            if exc.retryable:
                store.release(c)
                stats["failed"] += 1
            else:
                stats["permanent_failures"] += 1  # e.g. invalid address: keep the claim, no hourly retries
            logger.warning("Reminder not delivered (%s)", exc)
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Send due review reminders")
    parser.add_argument("--dry-run", action="store_true", help="build e-mails, send and write nothing")
    args = parser.parse_args(argv)
    db_url = (os.getenv("REMINDER_DB_URL") or "").strip()
    app_url, api_url = (os.getenv("APP_URL") or "").strip(), (os.getenv("API_URL") or "").strip()
    if not db_url or not app_url or not api_url:
        logger.info("Reminders not configured (REMINDER_DB_URL, APP_URL, API_URL); nothing to do.")
        return 0
    if args.dry_run:
        port = FakeEmailAdapter()
    else:
        key, sender = (os.getenv("RESEND_API_KEY") or "").strip(), (os.getenv("REMINDER_FROM") or "").strip()
        if not key or not sender:
            logger.info("Reminders not configured (RESEND_API_KEY, REMINDER_FROM); nothing to do.")
            return 0
        port = ResendEmailAdapter(key, sender)
    import psycopg2

    conn = psycopg2.connect(db_url, connect_timeout=15)
    try:
        stats = run(PostgresReminderStore(conn), port, app_url, api_url, dry_run=args.dry_run)
    finally:
        conn.close()
    logger.info("Reminder run: %s", stats)
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
