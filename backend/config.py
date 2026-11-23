"""
Application configuration loaded from environment variables.
Never commit secrets — use .env locally and platform env vars in production.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load the project-root .env file
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
# Real environment variables (platform/CI/shell) take precedence over the local .env file,
# so a stray .env in a deployed image can never override platform configuration.
load_dotenv(dotenv_path=_ENV_FILE, override=False)


def resolve_gemini_api_key(provider: str) -> str:
    """The key for Gemini calls (text generation and embeddings), one rule for both.

    GEMINI_API_KEY wins; LLM_API_KEY is the legacy name and is used only when GEMINI_API_KEY is
    unset and the provider is gemini. Chat used to prefer LLM_API_KEY while embeddings preferred
    GEMINI_API_KEY, so with both set and LLM_API_KEY stale, embeddings worked and chat got 401.
    """
    gemini = (os.getenv("GEMINI_API_KEY") or "").strip()
    if gemini:
        return gemini
    return (os.getenv("LLM_API_KEY") or "").strip() if provider == "gemini" else ""


def resolve_llm_api_key(provider: str) -> str:
    """The key for the configured text-generation provider. OpenAI uses only LLM_API_KEY."""
    if provider == "gemini":
        return resolve_gemini_api_key(provider)
    return (os.getenv("LLM_API_KEY") or "").strip()


def llm_api_keys_conflict(provider: str) -> bool:
    """True when both key variables are set, differ, and the provider is gemini (one is ignored)."""
    gemini = (os.getenv("GEMINI_API_KEY") or "").strip()
    legacy = (os.getenv("LLM_API_KEY") or "").strip()
    return provider == "gemini" and bool(gemini) and bool(legacy) and gemini != legacy


class Config:
    # ── General ──────────────────────────────────────────────────────────────
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    TESTING: bool = os.getenv("TESTING", "False").lower() == "true"
    # ── Security ─────────────────────────────────────────────────────────────
    # In production these must be set via environment variables.
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev-insecure-secret-key"
        if (os.getenv("DEBUG", "False").lower() == "true" or os.getenv("TESTING", "False").lower() == "true")
        else "",
    )
    LIBRIS_API_KEY: str = os.getenv(
        "LIBRIS_API_KEY",
        "dev-insecure-api-key"
        if (os.getenv("DEBUG", "False").lower() == "true" or os.getenv("TESTING", "False").lower() == "true")
        else "",
    )
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower() # gemini or openai
    # Effective keys after resolution (see resolve_llm_api_key), not the raw variables.
    LLM_API_KEY: str = resolve_llm_api_key(LLM_PROVIDER)
    GEMINI_API_KEY: str = resolve_gemini_api_key(LLM_PROVIDER)
    # flash-lite: fast, cheap, and the highest free-tier quota (2.5-flash-lite is closed to new users).
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # ── Reverse Proxy ─────────────────────────────────────────────────────────
    # Count of trusted reverse proxy headers (e.g. 1 for Render / Railway / Nginx).
    # Default: 1 in production, 0 in dev/testing unless explicitly overridden.
    NUM_PROXIES: int = int(
        os.getenv(
            "NUM_PROXIES",
            "0"
            if (os.getenv("DEBUG", "False").lower() == "true" or os.getenv("TESTING", "False").lower() == "true")
            else "1",
        )
    )

    # ── Paths ─────────────────────────────────────────────────────────────────
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH: str = os.path.join(BASE_DIR, "data", "books.csv")
    MODEL_DIR: str = os.path.join(BASE_DIR, "saved_model")
    MODEL_PATH: str = os.path.join(MODEL_DIR, "tfidf.pkl")

    # ── Google Books API ──────────────────────────────────────────────────────
    GOOGLE_BOOKS_API_KEY: str = os.getenv("GOOGLE_BOOKS_API_KEY", "")
    GOOGLE_BOOKS_API_URL: str = "https://www.googleapis.com/books/v1/volumes"

    # ── Supabase & JWT Authentication ────────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    SUPABASE_JWT_AUDIENCE: str = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    SUPABASE_JWT_ISSUER: str = os.getenv("SUPABASE_JWT_ISSUER", "")

    # ── Direct PostgreSQL / Local Integration ─────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Volatile in-memory repositories lose user data on restart. Production startup refuses
    # them unless this is explicitly enabled (disposable local/demo stacks only).
    ALLOW_IN_MEMORY_REPOSITORIES: bool = os.getenv("ALLOW_IN_MEMORY_REPOSITORIES", "False").lower() == "true"

    # ── ML Settings ───────────────────────────────────────────────────────────
    TOP_N_RECOMMENDATIONS: int = int(os.getenv("TOP_N_RECOMMENDATIONS", "10"))

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    # Largest accepted request body. The biggest legitimate body (a learning item) is ~41 KB, so
    # 1 MiB leaves ample headroom; Flask/werkzeug answers 413 above it, before JSON is parsed.
    MAX_REQUEST_BYTES: int = int(os.getenv("MAX_REQUEST_BYTES", str(1024 * 1024)))
    # Public web app address, used for links the API hands out (reminder unsubscribe redirect).
    APP_URL: str = os.getenv("APP_URL", "").rstrip("/")
    # Web Push (Faz 3): public half of the VAPID key pair; the private half lives only in the
    # reminder worker's secrets (VAPID_PRIVATE_KEY). Empty -> the push option stays hidden.
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    # Faz 5: FSRS scheduling instead of the fixed 1/3/7/14/30-day stages. Off until enabled.
    FSRS_ENABLED: bool = os.getenv("FSRS_ENABLED", "false").strip().lower() in ("1", "true", "yes")
