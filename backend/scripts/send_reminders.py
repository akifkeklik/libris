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
APP_URL (web), API_URL (backend, for the unsubscribe link); for Web Push VAPID_PRIVATE_KEY and
VAPID_SUBJECT ("mailto:you@your-domain"). Each channel runs only when configured; with neither
-> exits 0 with a notice, so the schedule does not fail before the operator has configured it.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.application.use_cases.reminders import (  # noqa: E402
    build_reminder_email,
    build_reminder_push,
)
from backend.infrastructure.email.resend_adapter import (  # noqa: E402
    EmailMessage,
    EmailSendError,
    FakeEmailAdapter,
    ResendEmailAdapter,
)
from backend.infrastructure.push.webpush_adapter import (  # noqa: E402
    FakePushAdapter,
    PushGone,
    PushSendError,
    WebPushAdapter,
)

logger = logging.getLogger("send_reminders")
COLUMNS = ("user_id", "email", "language", "local_date", "unsubscribe_token", "due_count", "first_question")
PUSH_COLUMNS = ("user_id", "language", "local_date", "due_count", "first_question")


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
                "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING 1",
                (c["user_id"], c["local_date"], c.get("channel", "email"), c["due_count"]))
            claimed = cur.fetchone() is not None
        self._conn.commit()
        return claimed

    def release(self, c: Dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM public.reminder_sends WHERE user_id = %s AND local_date = %s AND channel = %s",
                        (c["user_id"], c["local_date"], c.get("channel", "email")))
        self._conn.commit()

    def push_candidates(self, now: datetime.datetime) -> List[Dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM public.reminder_push_candidates(%s)", (now,))
            return [{**dict(zip(PUSH_COLUMNS, row)), "channel": "push"} for row in cur.fetchall()]

    def subscriptions(self, user_id: str) -> List[Dict[str, str]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT endpoint, p256dh, auth FROM public.push_subscriptions WHERE user_id = %s", (user_id,))
            return [dict(zip(("endpoint", "p256dh", "auth"), row)) for row in cur.fetchall()]

    def delete_subscription(self, endpoint: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM public.push_subscriptions WHERE endpoint = %s", (endpoint,))
        self._conn.commit()


def run(store, email_port, app_url: str, api_url: str, now: Optional[datetime.datetime] = None,
        dry_run: bool = False, push_port=None) -> Dict[str, int]:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    stats = {"candidates": 0, "sent": 0, "skipped": 0, "failed": 0, "permanent_failures": 0}
    for c in (store.candidates(now) if email_port is not None else []):
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
    if push_port is not None:
        stats.update(_run_push(store, push_port, app_url, now, dry_run))
    return stats


def _run_push(store, push_port, app_url: str, now: datetime.datetime, dry_run: bool) -> Dict[str, int]:
    """One notification per reader per local day, to every device they allowed. A device the push
    service reports gone (404/410) is deleted. If no device took it and an error was temporary,
    the claim is released so the next hour retries."""
    stats = {"push_candidates": 0, "push_sent": 0, "push_skipped": 0, "push_failed": 0, "push_gone": 0}
    for c in store.push_candidates(now):
        stats["push_candidates"] += 1
        subs = store.subscriptions(c["user_id"])
        payload = build_reminder_push(c, app_url)
        if not subs:
            stats["push_skipped"] += 1
            continue
        if not dry_run and not store.claim(c):
            stats["push_skipped"] += 1
            continue
        delivered, retry = False, False
        for sub in subs:
            try:
                push_port.send(sub, payload)
                delivered = True
            except PushGone:
                stats["push_gone"] += 1
                if not dry_run:
                    store.delete_subscription(sub["endpoint"])
            except PushSendError as exc:
                retry = retry or exc.retryable
                logger.warning("Push not delivered (%s)", exc)
        if delivered:
            stats["push_sent"] += 1
        else:
            stats["push_failed"] += 1
            if retry and not dry_run:
                store.release(c)
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Send due review reminders")
    parser.add_argument("--dry-run", action="store_true", help="build messages, send and write nothing")
    args = parser.parse_args(argv)
    env = lambda k: (os.getenv(k) or "").strip()  # noqa: E731
    db_url, app_url, api_url = env("REMINDER_DB_URL"), env("APP_URL"), env("API_URL")
    if not db_url or not app_url or not api_url:
        logger.info("Reminders not configured (REMINDER_DB_URL, APP_URL, API_URL); nothing to do.")
        return 0
    email_ready = bool(env("RESEND_API_KEY") and env("REMINDER_FROM"))
    push_ready = bool(env("VAPID_PRIVATE_KEY") and env("VAPID_SUBJECT"))
    if not email_ready and not push_ready:
        logger.info("No reminder channel configured (RESEND_API_KEY+REMINDER_FROM or VAPID_PRIVATE_KEY+VAPID_SUBJECT).")
        return 0
    if args.dry_run:
        email_port = FakeEmailAdapter() if email_ready else None
        push_port = FakePushAdapter() if push_ready else None
    else:
        email_port = ResendEmailAdapter(env("RESEND_API_KEY"), env("REMINDER_FROM")) if email_ready else None
        push_port = WebPushAdapter(env("VAPID_PRIVATE_KEY"), env("VAPID_SUBJECT")) if push_ready else None
    import psycopg2

    conn = psycopg2.connect(db_url, connect_timeout=15)
    try:
        stats = run(PostgresReminderStore(conn), email_port, app_url, api_url, dry_run=args.dry_run, push_port=push_port)
    finally:
        conn.close()
    logger.info("Reminder run: %s", stats)
    return 0 if stats["failed"] == 0 and stats.get("push_failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
