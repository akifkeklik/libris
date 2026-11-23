"""
Web Push (VAPID) delivery for review reminders, behind a small port so the worker can be tested
with a fake. pywebpush is imported lazily: only the reminder worker installs it.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class PushGone(Exception):
    """The push service no longer knows this subscription (404/410): delete it."""


class PushSendError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class WebPushAdapter:
    def __init__(self, private_key: str, subject: str, ttl_seconds: int = 12 * 3600, timeout: float = 15):
        if not subject.startswith(("mailto:", "https://")):
            raise ValueError("VAPID subject must be a mailto: or https: URL")
        self._key = private_key
        self._claims = {"sub": subject}
        self._ttl = ttl_seconds
        self._timeout = timeout

    def send(self, subscription: Dict[str, str], payload: Dict[str, Any]) -> None:
        from pywebpush import WebPushException, webpush

        try:
            webpush(
                subscription_info={"endpoint": subscription["endpoint"],
                                   "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]}},
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self._key,
                vapid_claims=dict(self._claims),  # pywebpush adds aud/exp to the dict it is given
                ttl=self._ttl,
                timeout=self._timeout,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                raise PushGone(f"subscription gone ({status})") from None
            retryable = status is None or status == 429 or status >= 500
            # The message never includes the endpoint (it is a per-device capability URL).
            raise PushSendError(f"push rejected ({status})", status, retryable) from None


class FakePushAdapter:
    def __init__(self, gone: Optional[set] = None, fail: Optional[Dict[str, bool]] = None):
        self.sent: List[tuple] = []
        self._gone = gone or set()
        self._fail = fail or {}

    def send(self, subscription: Dict[str, str], payload: Dict[str, Any]) -> None:
        ep = subscription["endpoint"]
        if ep in self._gone:
            raise PushGone("gone")
        if ep in self._fail:
            raise PushSendError("fail", 503 if self._fail[ep] else 400, retryable=self._fail[ep])
        self.sent.append((ep, payload))
