"""
Review reminders: the reader's preferences and the daily digest e-mail.

The e-mail is built here (pure, testable); delivery is the EmailPort's job and the hourly run is
backend/scripts/send_reminders.py. Texts follow the reader's chosen language.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LANGUAGES = ("en", "tr", "de", "es", "fr", "it")
CHANNELS = ("email", "push", "off")
SECONDS_PER_CARD = 30
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DEFAULTS = {"channel": "email", "local_time": "09:00", "timezone": "UTC", "quiet_days": [], "language": "en"}


def validate_preferences(data: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the cleaned preferences or raises ValueError naming the bad field."""
    out: Dict[str, Any] = {}
    channel = data.get("channel", DEFAULTS["channel"])
    if channel not in CHANNELS:
        raise ValueError("channel must be email, push or off")
    out["channel"] = channel
    local_time = str(data.get("local_time", DEFAULTS["local_time"]))[:5]
    if not _TIME.match(local_time):
        raise ValueError("local_time must be HH:MM")
    out["local_time"] = local_time
    tz = str(data.get("timezone", DEFAULTS["timezone"]))
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("timezone must be an IANA time zone such as Europe/Istanbul")
    out["timezone"] = tz
    quiet = data.get("quiet_days", [])
    if not isinstance(quiet, list) or any(not isinstance(d, int) or isinstance(d, bool) or not 0 <= d <= 6 for d in quiet):
        raise ValueError("quiet_days must be a list of weekday numbers 0 (Sunday) to 6")
    out["quiet_days"] = sorted(set(quiet))
    language = data.get("language", DEFAULTS["language"])
    if language not in LANGUAGES:
        raise ValueError("language must be one of " + ", ".join(LANGUAGES))
    out["language"] = language
    return out


class ReminderPreferencesUseCase:
    def __init__(self, repo):
        self._repo = repo

    def get(self, user_id: str, user_token: str) -> Dict[str, Any]:
        row = self._repo.get(user_id, user_token)
        return {**DEFAULTS, **(row or {}), "saved": row is not None}

    def update(self, user_id: str, user_token: str, email: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
        prefs = validate_preferences(data)
        # The address comes from the verified session, never from the request body.
        prefs["email"] = email or None
        self._repo.upsert(user_id, user_token, prefs)
        return {**prefs, "saved": True}


TEXT = {
    "en": {"subject": "{n} question waiting for you|{n} questions waiting for you",
           "intro": "You have {n} review question due today.|You have {n} review questions due today.",
           "minutes": "About {m} minute.|About {m} minutes.", "first": "First question:",
           "cta": "Start reviewing", "why": "You get this because daily reminders are on in your Libris settings.",
           "unsub": "Unsubscribe", "settings": "Change reminder settings"},
    "tr": {"subject": "Seni bekleyen {n} soru var|Seni bekleyen {n} soru var",
           "intro": "Bugün tekrar etmen gereken {n} soru var.|Bugün tekrar etmen gereken {n} soru var.",
           "minutes": "Yaklaşık {m} dakika.|Yaklaşık {m} dakika.", "first": "İlk soru:",
           "cta": "Tekrara başla", "why": "Bu e-postayı Libris ayarlarında günlük hatırlatma açık olduğu için alıyorsun.",
           "unsub": "Abonelikten çık", "settings": "Hatırlatma ayarlarını değiştir"},
    "de": {"subject": "{n} Frage wartet auf dich|{n} Fragen warten auf dich",
           "intro": "Heute ist {n} Wiederholungsfrage fällig.|Heute sind {n} Wiederholungsfragen fällig.",
           "minutes": "Etwa {m} Minute.|Etwa {m} Minuten.", "first": "Erste Frage:",
           "cta": "Jetzt wiederholen", "why": "Du erhältst diese E-Mail, weil tägliche Erinnerungen in deinen Libris-Einstellungen aktiv sind.",
           "unsub": "Abmelden", "settings": "Erinnerungen ändern"},
    "es": {"subject": "Tienes {n} pregunta pendiente|Tienes {n} preguntas pendientes",
           "intro": "Hoy tienes {n} pregunta de repaso.|Hoy tienes {n} preguntas de repaso.",
           "minutes": "Aproximadamente {m} minuto.|Aproximadamente {m} minutos.", "first": "Primera pregunta:",
           "cta": "Empezar el repaso", "why": "Recibes este correo porque tienes activados los recordatorios diarios en Libris.",
           "unsub": "Darse de baja", "settings": "Cambiar recordatorios"},
    "fr": {"subject": "{n} question vous attend|{n} questions vous attendent",
           "intro": "Vous avez {n} question à réviser aujourd'hui.|Vous avez {n} questions à réviser aujourd'hui.",
           "minutes": "Environ {m} minute.|Environ {m} minutes.", "first": "Première question :",
           "cta": "Commencer la révision", "why": "Vous recevez cet e-mail car les rappels quotidiens sont activés dans vos paramètres Libris.",
           "unsub": "Se désabonner", "settings": "Modifier les rappels"},
    "it": {"subject": "Hai {n} domanda in attesa|Hai {n} domande in attesa",
           "intro": "Oggi hai {n} domanda da ripassare.|Oggi hai {n} domande da ripassare.",
           "minutes": "Circa {m} minuto.|Circa {m} minuti.", "first": "Prima domanda:",
           "cta": "Inizia il ripasso", "why": "Ricevi questa e-mail perché i promemoria giornalieri sono attivi nelle impostazioni di Libris.",
           "unsub": "Annulla l'iscrizione", "settings": "Cambia i promemoria"},
}


def _plural(text: str, n: int) -> str:
    one, many = text.split("|")
    return one if n == 1 else many


@dataclass
class ReminderEmail:
    subject: str
    html: str
    text: str
    headers: Dict[str, str]


def build_reminder_email(candidate: Dict[str, Any], app_url: str, api_url: str) -> ReminderEmail:
    lang = candidate.get("language") if candidate.get("language") in TEXT else "en"
    t = TEXT[lang]
    n = int(candidate["due_count"])
    minutes = max(1, math.ceil(n * SECONDS_PER_CARD / 60))
    review_url = f"{app_url.rstrip('/')}/learning?utm_source=reminder&reminder_date={candidate['local_date']}"
    settings_url = f"{app_url.rstrip('/')}/settings#reminders"
    unsub_url = f"{api_url.rstrip('/')}/api/reminders/unsubscribe?token={candidate['unsubscribe_token']}"
    subject = _plural(t["subject"], n).format(n=n)
    intro = _plural(t["intro"], n).format(n=n)
    mins = _plural(t["minutes"], minutes).format(m=minutes)
    question = (candidate.get("first_question") or "").strip()[:300]
    lines: List[str] = [intro, mins, ""]
    if question:
        lines += [t["first"], question, ""]
    lines += [f"{t['cta']}: {review_url}", "", t["why"], f"{t['settings']}: {settings_url}", f"{t['unsub']}: {unsub_url}"]
    e = html.escape
    body = (
        f'<div style="font-family:Georgia,serif;max-width:520px;margin:auto;color:#1a1a2a">'
        f"<p>{e(intro)} {e(mins)}</p>"
        + (f'<p style="color:#555">{e(t["first"])}</p><blockquote style="border-left:3px solid #00769f;margin:0;padding:0.5em 1em">{e(question)}</blockquote>' if question else "")
        + f'<p><a href="{e(review_url)}" style="display:inline-block;background:#00769f;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none">{e(t["cta"])}</a></p>'
        f'<p style="font-size:12px;color:#666">{e(t["why"])} <a href="{e(settings_url)}">{e(t["settings"])}</a> · <a href="{e(unsub_url)}">{e(t["unsub"])}</a></p></div>'
    )
    headers = {"List-Unsubscribe": f"<{unsub_url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    return ReminderEmail(subject=subject, html=body, text="\n".join(lines), headers=headers)


# ── Web Push ─────────────────────────────────────────────────────────────────

_B64URL = re.compile(r"^[A-Za-z0-9_-]+=*$")


def validate_push_subscription(data: Dict[str, Any]) -> Dict[str, str]:
    """The browser's PushSubscription.toJSON(): {endpoint, keys: {p256dh, auth}}."""
    endpoint = data.get("endpoint") if isinstance(data, dict) else None
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or len(endpoint) > 1024:
        raise ValueError("endpoint must be an https URL")
    if not isinstance(keys, dict):
        raise ValueError("keys are required")
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not isinstance(p256dh, str) or not 40 <= len(p256dh) <= 200 or not _B64URL.match(p256dh):
        raise ValueError("keys.p256dh is invalid")
    if not isinstance(auth, str) or not 8 <= len(auth) <= 100 or not _B64URL.match(auth):
        raise ValueError("keys.auth is invalid")
    return {"endpoint": endpoint, "p256dh": p256dh, "auth": auth}


def build_reminder_push(candidate: Dict[str, Any], app_url: str) -> Dict[str, str]:
    """Notification payload. Shows the count and time only: lock screens are visible to others,
    so the question text stays out of push notifications."""
    lang = candidate.get("language") if candidate.get("language") in TEXT else "en"
    t = TEXT[lang]
    n = int(candidate["due_count"])
    minutes = max(1, math.ceil(n * SECONDS_PER_CARD / 60))
    return {
        "title": _plural(t["subject"], n).format(n=n),
        "body": _plural(t["minutes"], minutes).format(m=minutes),
        "url": f"{app_url.rstrip('/')}/learning?utm_source=reminder&reminder_channel=push&reminder_date={candidate['local_date']}",
        "tag": "libris-review-reminder",
    }


# ── Product events ───────────────────────────────────────────────────────────

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """Only known events with known, small properties are stored (no free text)."""
    event = data.get("event") if isinstance(data, dict) else None
    props = data.get("props") or {}
    if not isinstance(props, dict):
        raise ValueError("props must be an object")
    if event == "reminder_opened":
        channel = props.get("channel", "email")
        date = props.get("reminder_date")
        if channel not in ("email", "push"):
            raise ValueError("channel must be email or push")
        if date is not None and (not isinstance(date, str) or not _DATE.match(date)):
            raise ValueError("reminder_date must be YYYY-MM-DD")
        return {"event": event, "props": {"channel": channel, **({"reminder_date": date} if date else {})}}
    if event == "review_session_completed":
        count = props.get("reviewed_count")
        if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 1000:
            raise ValueError("reviewed_count must be a number between 0 and 1000")
        return {"event": event, "props": {"reviewed_count": count}}
    raise ValueError("unknown event")
