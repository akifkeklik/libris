"""
Reader tool endpoints on the activity blueprint: reminder preferences and unsubscribe, Web Push
subscriptions, product events (Faz 3), imports (Faz 4), card controls, review settings and the
Anki export (Faz 5). Split out of routes.py without changing any URL, endpoint name or behaviour.
"""

import logging

from flask import g, jsonify, request

from ..container import container
from .routes import _ai_budget_left, activity_bp, rate_limit_ai, require_auth

logger = logging.getLogger("backend.routes.routes")  # same logger name as before the split


# ─────────────────────────────────────────────────────────────────────────────


@activity_bp.route("/reminders/preferences", methods=["GET", "PUT"])
@require_auth
def reminder_preferences():
    use_case = getattr(container, "reminder_prefs_uc", None)
    if use_case is None:
        return jsonify({"error": "Reminders are not available on this server"}), 503
    token = getattr(g, "jwt_token", None)
    try:
        if request.method == "GET":
            return jsonify(use_case.get(g.user_id, token)), 200
        email = getattr(getattr(g, "user", None), "email", None)
        return jsonify(use_case.update(g.user_id, token, email, request.get_json(silent=True) or {})), 200
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.error("Reminder preferences failed: %s", type(exc).__name__)
        return jsonify({"error": "Reminder settings are temporarily unavailable"}), 503


@activity_bp.route("/reminders/unsubscribe", methods=["GET", "POST"])
def reminders_unsubscribe():
    """One-click unsubscribe from the e-mail (no login). GET redirects to a page in the reader's
    language; POST is the RFC 8058 List-Unsubscribe-Post request from mail clients."""
    import uuid as _uuid

    from ..config import Config

    token = (request.args.get("token") or "").strip()
    ok = False
    try:
        _uuid.UUID(token)
        repo = getattr(container, "reminder_repo", None)
        ok = bool(repo and repo.unsubscribe(token))
    except ValueError:
        ok = False
    except Exception as exc:
        logger.error("Unsubscribe failed: %s", type(exc).__name__)
    if request.method == "POST":
        return jsonify({"unsubscribed": ok}), 200
    if Config.APP_URL:
        from flask import redirect
        return redirect(f"{Config.APP_URL}/reminders/unsubscribed?status={'ok' if ok else 'invalid'}", code=303)
    return jsonify({"unsubscribed": ok}), 200


@activity_bp.route("/reminders/push-key", methods=["GET"])
@require_auth
def reminder_push_key():
    """The VAPID public key the browser subscribes with; empty when push is not configured."""
    from ..config import Config

    return jsonify({"public_key": Config.VAPID_PUBLIC_KEY or None}), 200


@activity_bp.route("/reminders/push-subscription", methods=["POST", "DELETE"])
@require_auth
def reminder_push_subscription():
    from ..application.use_cases.reminders import validate_push_subscription

    repo = getattr(container, "reminder_repo", None)
    if repo is None:
        return jsonify({"error": "Reminders are not available on this server"}), 503
    token = getattr(g, "jwt_token", None)
    data = request.get_json(silent=True) or {}
    try:
        if request.method == "POST":
            repo.save_push_subscription(token, validate_push_subscription(data))
            return jsonify({"subscribed": True}), 200
        endpoint = data.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ValueError("endpoint must be an https URL")
        repo.delete_push_subscription(g.user_id, token, endpoint)
        return jsonify({"subscribed": False}), 200
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.error("Push subscription failed: %s", type(exc).__name__)
        return jsonify({"error": "Push notifications are temporarily unavailable"}), 503


@activity_bp.route("/events", methods=["POST"])
@require_auth
def record_product_event():
    """First-party product events (reminder_opened, review_session_completed). Never blocks the UI:
    the client fires and forgets; failures are logged by type only."""
    from ..application.use_cases.reminders import validate_event

    repo = getattr(container, "reminder_repo", None)
    if repo is None:
        return jsonify({"recorded": False}), 202
    try:
        repo.record_event(g.user_id, getattr(g, "jwt_token", None), validate_event(request.get_json(silent=True) or {}))
        return jsonify({"recorded": True}), 201
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.warning("Product event not recorded: %s", type(exc).__name__)
        return jsonify({"recorded": False}), 202


# ─────────────────────────────────────────────────────────────────────────────
# Imports (Faz 4): Kindle / Readwise / Goodreads -> approval queue -> notes and shelves
# ─────────────────────────────────────────────────────────────────────────────

IMPORT_MAX_BYTES = 6 * 1024 * 1024


def _import_uc_or_503():
    uc = getattr(container, "import_uc", None)
    if uc is None:
        return None, (jsonify({"error": "Imports are not available on this server"}), 503)
    return uc, None


@activity_bp.route("/imports", methods=["POST"])
@require_auth
def create_import():
    """Body: {source: kindle|readwise|goodreads, text: <file contents>}. Larger body limit than the
    rest of the API (a Kindle clippings file is often a few MB); still bounded."""
    request.max_content_length = IMPORT_MAX_BYTES
    uc, err = _import_uc_or_503()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        summary = uc.import_text(g.user_id, getattr(g, "jwt_token", None), str(data.get("source") or ""), data.get("text"))
        return jsonify(summary), 201
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.error("Import failed: %s", type(exc).__name__)
        return jsonify({"error": "The import could not be processed right now"}), 503


@activity_bp.route("/imports/pending", methods=["GET"])
@require_auth
def list_import_queue():
    uc, err = _import_uc_or_503()
    if err:
        return err
    try:
        limit = int(request.args.get("limit", 200))
        return jsonify(uc.list_pending(g.user_id, getattr(g, "jwt_token", None), limit)), 200
    except ValueError:
        return jsonify({"error": "limit must be a number"}), 400
    except Exception as exc:
        logger.error("Import queue failed: %s", type(exc).__name__)
        return jsonify({"error": "The import queue is temporarily unavailable"}), 503


@activity_bp.route("/imports/decide", methods=["POST"])
@require_auth
def decide_imports():
    """Body: {action: approve|reject, ids: [...], highlight_as?: key_takeaway|personal_note,
    book_overrides?: {item_id: isbn13}}."""
    uc, err = _import_uc_or_503()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    token = getattr(g, "jwt_token", None)
    try:
        if data.get("action") == "reject":
            return jsonify({"rejected": uc.reject(g.user_id, token, data.get("ids"))}), 200
        if data.get("action") == "approve":
            overrides = data.get("book_overrides") or {}
            if not isinstance(overrides, dict):
                raise ValueError("book_overrides must be an object")
            return jsonify(uc.approve(g.user_id, token, data.get("ids"), str(data.get("highlight_as") or "key_takeaway"),
                                      overrides, generate_questions=_ai_budget_left(g.user_id))), 200
        raise ValueError("action must be approve or reject")
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.error("Import decision failed: %s", type(exc).__name__)
        return jsonify({"error": "The import queue is temporarily unavailable"}), 503


# ── Faz 5: card controls, review settings, Anki export ───────────────────────


def _card_controls():
    uc = getattr(container, "card_controls_uc", None)
    if uc is None:
        return None, (jsonify({"error": "Card controls are not available on this server"}), 503)
    return uc, None


@activity_bp.route("/learning/items/<item_id>/regenerate", methods=["POST"])
@require_auth
@rate_limit_ai
def regenerate_learning_item(item_id: str):
    uc, err = _card_controls()
    if err:
        return err
    try:
        return jsonify({"status": "success", "item": uc.regenerate(g.user_id, item_id)}), 200
    except LookupError:
        return jsonify({"error": "Review item not found or access denied"}), 404
    except PermissionError as exc:
        return jsonify({"error": str(exc), "reason": "limit"}), 429
    except RuntimeError as exc:
        return jsonify({"error": str(exc), "reason": "unavailable"}), 503


@activity_bp.route("/learning/items/<item_id>/report", methods=["POST"])
@require_auth
def report_learning_item(item_id: str):
    uc, err = _card_controls()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        uc.report(g.user_id, item_id, str(data.get("reason") or ""), str(data.get("comment") or ""))
        return jsonify({"status": "success"}), 200
    except LookupError:
        return jsonify({"error": "Review item not found or access denied"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@activity_bp.route("/learning/settings", methods=["GET", "PUT"])
@require_auth
def learning_settings():
    uc, err = _card_controls()
    if err:
        return err
    token = getattr(g, "jwt_token", None)
    try:
        if request.method == "GET":
            return jsonify(uc.get_settings(g.user_id, token)), 200
        return jsonify(uc.save_settings(g.user_id, token, request.get_json(silent=True) or {})), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("Learning settings failed: %s", type(exc).__name__)
        return jsonify({"error": "Review settings are temporarily unavailable"}), 503


@activity_bp.route("/learning/export/anki", methods=["GET"])
@require_auth
def export_learning_anki():
    """All active and paused review cards as an Anki package (.apkg)."""
    from flask import Response

    uc, err = _card_controls()
    if err:
        return err
    try:
        data = uc.export_anki(g.user_id)
    except Exception as exc:
        logger.error("Anki export failed: %s", type(exc).__name__)
        return jsonify({"error": "The export could not be created right now"}), 503
    return Response(data, mimetype="application/octet-stream", headers={
        "Content-Disposition": 'attachment; filename="libris-cards.apkg"',
        "Cache-Control": "no-store, private",
    })
