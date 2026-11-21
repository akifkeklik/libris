"""
Gemini key resolution and LLM failure categories.

Production incident (2026-11-21): GEMINI_API_KEY was rotated and LLM_API_KEY kept the old key.
Embeddings preferred GEMINI_API_KEY and recovered; chat preferred LLM_API_KEY and kept getting
401, which RAG served as a grounded fallback with nothing saying why. These tests pin:

  * one resolution rule for chat and embeddings (GEMINI_API_KEY first, LLM_API_KEY legacy);
  * the adapter reports why a call failed ("auth", "rate_limited", ...), per thread;
  * a RAG fallback carries that category in metrics.llm_error and is still not cached.

Offline: HTTP is a fake requests session; sockets are refused by the grounding fixture.
"""

import threading
from unittest.mock import MagicMock

import pytest
import requests
from backend.config import llm_api_keys_conflict, resolve_gemini_api_key, resolve_llm_api_key
from backend.infrastructure.llm.adapters import GenericLlmAdapter, classify_llm_error
from backend.infrastructure.llm.gemini_rest import GeminiError, GeminiRestClient
from backend.services.embedding_service import EmbeddingService
from backend.tests import test_rag_grounding as grounding
from backend.tests.test_rag_grounding import QUERY, _use_case

pytestmark = pytest.mark.unit

recommender = grounding.recommender
_no_network = grounding._no_network


def _env(monkeypatch, **values):
    for name in ("GEMINI_API_KEY", "LLM_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


# ── Key resolution ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("env, provider, expected", [
    ({"GEMINI_API_KEY": "new", "LLM_API_KEY": "stale"}, "gemini", "new"),   # the incident
    ({"LLM_API_KEY": "legacy"}, "gemini", "legacy"),                         # legacy-only setups keep working
    ({"GEMINI_API_KEY": "new"}, "gemini", "new"),
    ({"GEMINI_API_KEY": "  "}, "gemini", ""),                                # whitespace is not a key
    ({"GEMINI_API_KEY": "g", "LLM_API_KEY": "sk-openai"}, "openai", "sk-openai"),
    ({"GEMINI_API_KEY": "g"}, "openai", ""),                                 # never send a Gemini key to OpenAI
])
def test_chat_key_resolution(monkeypatch, env, provider, expected):
    _env(monkeypatch, **env)
    assert resolve_llm_api_key(provider) == expected


@pytest.mark.parametrize("env", [
    {"GEMINI_API_KEY": "new", "LLM_API_KEY": "stale"},
    {"LLM_API_KEY": "legacy"},
    {"GEMINI_API_KEY": "new"},
])
def test_chat_and_embeddings_use_the_same_key(monkeypatch, env):
    _env(monkeypatch, LLM_PROVIDER="gemini", **env)
    assert EmbeddingService()._api_key == resolve_llm_api_key("gemini") == resolve_gemini_api_key("gemini")


def test_embeddings_still_use_gemini_when_chat_is_openai(monkeypatch):
    _env(monkeypatch, LLM_PROVIDER="openai", GEMINI_API_KEY="g", LLM_API_KEY="sk-openai")
    assert EmbeddingService()._api_key == "g"
    assert resolve_llm_api_key("openai") == "sk-openai"


@pytest.mark.parametrize("env, conflict", [
    ({"GEMINI_API_KEY": "a", "LLM_API_KEY": "b"}, True),
    ({"GEMINI_API_KEY": "a", "LLM_API_KEY": "a"}, False),
    ({"GEMINI_API_KEY": "a"}, False),
    ({"LLM_API_KEY": "b"}, False),
])
def test_conflicting_keys_are_detected(monkeypatch, env, conflict):
    _env(monkeypatch, **env)
    assert llm_api_keys_conflict("gemini") is conflict
    assert llm_api_keys_conflict("openai") is False


def test_embedding_service_imports_the_way_the_backfill_script_does():
    # backfill_embeddings.py puts backend/ on sys.path and imports `services.embedding_service`
    # as a top-level package; an absolute `backend.` import inside it broke that script once.
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[1]
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import config; "
            "from services.embedding_service import EmbeddingService; print('ok')")
    out = subprocess.run([sys.executable, "-c", code, str(backend_dir)], capture_output=True, text=True,
                         timeout=120, cwd=str(backend_dir.parent / "web"))  # cwd without a backend/ package
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().endswith("ok")


# ── Failure categories ───────────────────────────────────────────────────────


@pytest.mark.parametrize("exc, category", [
    (GeminiError("bad key", 401), "auth"),
    (GeminiError("forbidden", 403), "auth"),
    (GeminiError("quota", 429), "rate_limited"),
    (GeminiError("overloaded", 503), "provider_unavailable"),
    (GeminiError("bad payload", 400), "bad_request"),
    (requests.exceptions.ReadTimeout("slow"), "timeout"),
    (requests.exceptions.ConnectionError("dns"), "network"),
    (ValueError("unexpected"), "error"),
    (None, "empty_response"),
])
def test_classify_llm_error(exc, category):
    assert classify_llm_error(exc) == category


class _FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def _session(status, body):
    session = MagicMock()
    session.post.return_value = _FakeResponse(status, body)
    return session


def _adapter(status, body):
    adapter = GenericLlmAdapter(provider="gemini", api_key="test-key")
    adapter._gemini = GeminiRestClient("test-key", session=_session(status, body), retry_wait_seconds=0)
    return adapter


def test_adapter_reports_auth_failure_and_clears_it_on_success():
    adapter = _adapter(401, {"error": {"message": "API key not valid"}})
    assert adapter.generate_response("sys", "user") is None
    assert adapter.last_error == "auth"

    ok = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
    adapter._gemini = GeminiRestClient("test-key", session=_session(200, ok), retry_wait_seconds=0)
    assert adapter.generate_response("sys", "user") == "hello"
    assert adapter.last_error is None


def test_adapter_rate_limit_is_retried_once_then_reported():
    adapter = _adapter(429, {"error": {"message": "quota"}})
    assert adapter.generate_response("sys", "user") is None
    assert adapter.last_error == "rate_limited"
    assert adapter._gemini._session.post.call_count == 2


def test_adapter_without_key_is_not_configured():
    adapter = GenericLlmAdapter(provider="gemini", api_key="")
    assert adapter.generate_response("sys", "user") is None
    assert adapter.last_error == "not_configured"


def test_failure_category_is_per_thread():
    # One shared adapter, as in the app. The failing call finishes first, then the successful one;
    # each thread then reads last_error and must see its own outcome.
    adapter = GenericLlmAdapter(provider="gemini", api_key="test-key")
    failed, succeeded = threading.Event(), threading.Event()
    seen = {}

    def generate_text(prompt, **kwargs):
        if prompt == "fail":
            raise GeminiError("bad key", 401)
        failed.wait(timeout=5)
        return "fine"

    adapter._gemini = MagicMock()
    adapter._gemini.generate_text.side_effect = generate_text

    def run(name):
        adapter.generate_response("sys", name)
        if name == "fail":
            failed.set()
            succeeded.wait(timeout=5)  # the other thread's success has happened by now
        else:
            succeeded.set()
        seen[name] = adapter.last_error

    threads = [threading.Thread(target=run, args=("fail",)), threading.Thread(target=run, args=("work",))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen == {"fail": "auth", "work": None}


def test_error_log_names_the_category_but_not_the_key(caplog):
    adapter = _adapter(401, {"error": {"message": "API key not valid. key=AIzaLeakedValue123"}})
    with caplog.at_level("ERROR"):
        adapter.generate_response("sys", "user")
    record = next(r for r in caplog.records if r.getMessage() == "LLM provider error")
    data = record.extra_data
    assert data["error_category"] == "auth" and data["http_status"] == 401
    assert "AIzaLeakedValue123" not in str(data) and "test-key" not in str(data)


# ── RAG: the fallback says why ───────────────────────────────────────────────


def test_rag_fallback_reports_auth_failure_and_is_not_cached(recommender):
    uc, _, _ = _use_case(recommender)
    adapter = _adapter(401, {"error": {"message": "API key not valid"}})
    uc._llm_port = adapter

    first = uc.execute(QUERY)
    assert first["status"] == "llm_fallback"
    assert first["metrics"]["source"] == "grounded_fallback"
    assert first["metrics"]["llm_error"] == "auth"

    uc.execute(QUERY)  # not cached: Gemini is asked again
    assert adapter._gemini._session.post.call_count == 2


def test_rag_fallback_when_the_port_raises(recommender):
    uc, _, _ = _use_case(recommender, llm_error=RuntimeError("boom"))
    res = uc.execute(QUERY)
    assert res["status"] == "llm_fallback"
    assert res["metrics"]["llm_error"] == "port_exception"


def test_successful_generation_has_no_llm_error(recommender):
    uc, _, _ = _use_case(recommender, llm_answer='{"answer": "Two history books.", "explanations": {}}')
    res = uc.execute(QUERY)
    assert res["metrics"]["source"] == "rag_llm"
    assert "llm_error" not in res["metrics"]


@pytest.mark.parametrize("key, logged", [("", True), ("a-key", False)])
def test_missing_key_is_logged_once_at_startup(monkeypatch, caplog, key, logged):
    from backend import container as container_module
    from backend.config import Config

    monkeypatch.setattr(Config, "LLM_API_KEY", key)
    monkeypatch.setattr(Config, "LLM_PROVIDER", "gemini")
    with caplog.at_level("ERROR", logger="backend.container"):
        container_module.Container(recommender=MagicMock())
    messages = [r.getMessage() for r in caplog.records if r.name == "backend.container"]
    assert any("No API key for LLM_PROVIDER=gemini" in m for m in messages) is logged
    assert key == "" or all(key not in m for m in messages)
