"""
Optional Sentry error tracking for the API. Off unless SENTRY_DSN is set.

Privacy: Libris stores reading notes, questions and e-mail addresses. None of that may reach
Sentry, so every event and breadcrumb passes through scrub_event / scrub_breadcrumb:
  * no user identity (data_collection user_info=False, and event["user"] is cleared);
  * request: only method and path; no body, cookies, query string or environment, and only a
    short allowlist of headers (never Authorization or X-Api-Key);
  * no `extra` data except the request id; no stack-frame local variables;
  * exception messages are dropped (type and stack trace are kept): they can quote user text;
  * log events keep only the message template (never its arguments); e-mail addresses are
    masked and long text is truncated in what remains.
The SDK is also told not to collect any of this (data_collection), so scrubbing is a second layer.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ALLOWED_HEADERS = {"user-agent", "content-type", "x-request-id"}
_MAX_TEXT = 300


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = _EMAIL.sub("[email]", value)
    return text if len(text) <= _MAX_TEXT else text[:_MAX_TEXT] + "…[truncated]"


def scrub_event(event: Dict[str, Any], hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    event["user"] = {}
    request = event.get("request")
    if isinstance(request, dict):
        url = request.get("url")
        kept = {"method": request.get("method"), "url": url.split("?", 1)[0] if isinstance(url, str) else None}
        headers = request.get("headers") or {}
        if isinstance(headers, dict):
            kept["headers"] = {k: v for k, v in headers.items() if str(k).lower() in _ALLOWED_HEADERS}
        event["request"] = {k: v for k, v in kept.items() if v is not None}
    extra = event.get("extra")
    event["extra"] = {"request_id": extra["request_id"]} if isinstance(extra, dict) and "request_id" in extra else {}
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        # The template ("sync failed for %s") identifies the log line; its params may be user data.
        event["logentry"] = {"message": _clean_text(logentry.get("message"))}
        event.pop("message", None)
    elif "message" in event:
        event["message"] = _clean_text(event["message"])
    for exc in (event.get("exception") or {}).get("values") or []:
        if exc.get("value"):
            exc["value"] = "[redacted]"
        for frame in (exc.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    for crumb in (event.get("breadcrumbs") or {}).get("values") or []:
        scrub_breadcrumb(crumb)
    return event


def scrub_breadcrumb(crumb: Dict[str, Any], hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    crumb.pop("data", None)
    record = (hint or {}).get("log_record")
    if record is not None:
        # Logging breadcrumbs carry the formatted line, arguments included ("opened note: <text>").
        # Keep only the template, as for log events.
        crumb["message"] = str(getattr(record, "msg", ""))
    if crumb.get("category") == "httplib" or crumb.get("type") == "http":
        crumb.pop("message", None)  # outgoing URLs can carry search text in their query string
    if "message" in crumb:
        crumb["message"] = _clean_text(crumb["message"])
    return crumb


def init_error_tracking(environ: Optional[Dict[str, str]] = None, **overrides: Any) -> bool:
    """Starts Sentry when SENTRY_DSN is set; returns whether it was started. Never raises."""
    env = os.environ if environ is None else environ
    dsn = (env.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=env.get("SENTRY_ENVIRONMENT") or "production",
            release=env.get("SENTRY_RELEASE") or env.get("RENDER_GIT_COMMIT") or None,
            data_collection={
                "user_info": False,
                "cookies": {"mode": "off"},
                "http_headers": {"request": {"mode": "allowlist", "terms": sorted(_ALLOWED_HEADERS)}},
                "http_bodies": [],
                "url_query_params": {"mode": "off"},
                "gen_ai": {"inputs": False, "outputs": False},
                "database_query_data": False,
                "stack_frame_variables": False,
            },
            traces_sample_rate=float(env.get("SENTRY_TRACES_SAMPLE_RATE") or 0.0),
            before_send=scrub_event,
            before_breadcrumb=scrub_breadcrumb,
            **overrides,
        )
        logger.info("Error tracking enabled (Sentry).")
        return True
    except Exception as exc:  # a monitoring failure must never stop the API
        logger.warning("Error tracking could not start: %s", type(exc).__name__)
        return False
