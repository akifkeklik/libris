import logging
import re
import threading
import time
from typing import Optional

from ...domain.ports import LlmPort
from .gemini_rest import DEFAULT_TEXT_MODEL, GeminiError, GeminiRestClient

logger = logging.getLogger(__name__)


def _sanitize_secret(msg: str) -> str:
    """Removes API keys or authorization tokens from error messages and logs."""
    if not msg:
        return ""
    sanitized = re.sub(
        r"(key|api_key|token|password|secret)=[A-Za-z0-9_\-\.]+",
        r"\1=REDACTED",
        str(msg),
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9_\-\.]+",
        "Bearer REDACTED",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


def classify_llm_error(exc: Optional[BaseException]) -> str:
    """Why a generation call failed, as a short category safe to log and return in metrics.

    "auth" (401/403: missing, invalid or revoked key) is a configuration error that retrying
    cannot fix; "rate_limited" (429) and "provider_unavailable" (5xx) are transient.
    """
    if exc is None:
        return "empty_response"
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status in (401, 403):
            return "auth"
        if status == 429:
            return "rate_limited"
        if status >= 500:
            return "provider_unavailable"
        if 400 <= status < 500:
            return "bad_request"
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "connection" in name:
        return "network"
    return "error"


class GenericLlmAdapter(LlmPort):
    def __init__(self, provider: str, api_key: str, model_name: Optional[str] = None):
        self._provider = provider
        self._api_key = api_key
        self._model_name = model_name or (DEFAULT_TEXT_MODEL if provider == "gemini" else "gpt-3.5-turbo")
        self._gemini = GeminiRestClient(api_key) if api_key and provider == "gemini" else None
        self._openai_client = None
        self._lock = threading.Lock()
        self.last_latency_ms: float = 0.0
        # Per thread, so a caller reads the outcome of its own call, not a concurrent request's.
        self._outcome = threading.local()

    @property
    def last_error(self) -> Optional[str]:
        """Category of this thread's last failed call (classify_llm_error), or None on success."""
        return getattr(self._outcome, "error", None)

    def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        self._outcome.error = None
        if not self._api_key:
            self._outcome.error = "not_configured"
            logger.error("No API key for the LLM provider (set GEMINI_API_KEY for gemini).")
            return None

        t0 = time.time()
        try:
            if self._provider == "gemini":
                text = self._gemini.generate_text(
                    user_prompt, model=self._model_name, temperature=0.3, timeout=15.0,
                    system_instruction=system_prompt,
                )
                lat = round((time.time() - t0) * 1000, 2)
                with self._lock:
                    self.last_latency_ms = lat
                if text is None:
                    self._outcome.error = "empty_response"
                    logger.warning("Gemini returned no text (safety filter or empty response).")
                return text

            elif self._provider == "openai":
                if self._openai_client is None:
                    with self._lock:
                        if self._openai_client is None:
                            from openai import OpenAI
                            self._openai_client = OpenAI(api_key=self._api_key, timeout=15.0)

                response = self._openai_client.chat.completions.create(
                    model=self._model_name,
                    temperature=0.3,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                lat = round((time.time() - t0) * 1000, 2)
                with self._lock:
                    self.last_latency_ms = lat
                return response.choices[0].message.content
            else:
                self._outcome.error = "not_configured"
                logger.error(f"Unsupported LLM provider: {self._provider}")
                return None

        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            with self._lock:
                self.last_latency_ms = lat
            clean_err = _sanitize_secret(str(e))
            category = classify_llm_error(e)
            self._outcome.error = category
            logger.error(
                "LLM provider error",
                extra={
                    "extra_data": {
                        "provider": self._provider,
                        "model": self._model_name,
                        "error": clean_err,
                        "error_type": type(e).__name__,
                        "error_category": category,
                        "http_status": getattr(e, "status", None) if isinstance(e, GeminiError) else None,
                        "latency_ms": lat,
                    }
                },
            )
            return None
