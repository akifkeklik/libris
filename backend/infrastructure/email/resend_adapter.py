"""
E-mail delivery behind a small port, so the provider can be swapped and tests never send mail.

ResendEmailAdapter talks to Resend's HTTP API (POST https://api.resend.com/emails). The API key is
sent in the Authorization header and is never logged; errors keep only the HTTP status and the
provider's error name.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str
    headers: Dict[str, str] = field(default_factory=dict)


class EmailSendError(RuntimeError):
    def __init__(self, message: str, status: int = 0, retryable: bool = True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class ResendEmailAdapter:
    def __init__(self, api_key: str, sender: str, session: Optional[requests.Session] = None, timeout: float = 15.0):
        if not api_key or not sender:
            raise ValueError("RESEND_API_KEY and REMINDER_FROM are required")
        self._api_key, self._sender = api_key, sender
        self._session = session or requests.Session()
        self._timeout = timeout

    def send(self, message: EmailMessage) -> str:
        payload = {"from": self._sender, "to": [message.to], "subject": message.subject,
                   "html": message.html, "text": message.text, "headers": message.headers}
        try:
            resp = self._session.post(RESEND_URL, json=payload, timeout=self._timeout,
                                      headers={"Authorization": f"Bearer {self._api_key}"})
        except requests.RequestException as exc:
            raise EmailSendError(f"network error: {type(exc).__name__}") from exc
        if resp.status_code >= 300:
            try:
                name = resp.json().get("name", "")
            except ValueError:
                name = ""
            # 4xx other than 429 will not succeed on retry (bad address, unverified domain, ...).
            retryable = resp.status_code == 429 or resp.status_code >= 500
            raise EmailSendError(f"resend {resp.status_code} {name}".strip(), resp.status_code, retryable)
        return str((resp.json() or {}).get("id", ""))


class FakeEmailAdapter:
    """Records messages instead of sending them (tests, dry runs)."""

    def __init__(self, fail_for: Optional[List[str]] = None):
        self.sent: List[EmailMessage] = []
        self._fail_for = set(fail_for or [])

    def send(self, message: EmailMessage) -> str:
        if message.to in self._fail_for:
            raise EmailSendError("fake failure", 503)
        self.sent.append(message)
        return f"fake-{len(self.sent)}"
