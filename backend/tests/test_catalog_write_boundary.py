"""Security regression tests for the shared catalog (public.books, public.book_embeddings).

Contract these tests pin down:
  * Clients (anon / authenticated) never write public.books directly. Readers add books only
    through the SECURITY DEFINER RPC add_catalog_book (migration 15), with their own JWT.
  * No runtime code (backend or web) writes either catalog table over the REST API, except the
    one known best-effort embedding upsert, which is listed explicitly so a new write path fails.
  * The runtime backend never loads a service_role / secret key; only the offline ingestion
    script does.
  * Hardening draft 01c (catalog-only, independent of 01b) closes every client write path on
    books and book_embeddings and keeps every read path the app and the AI/RAG system need
    (books SELECT, book_embeddings SELECT, the vector RPCs and add_catalog_book EXECUTE). It
    never touches add_catalog_book, ownership, FORCE RLS or service_role.

The database-side behaviour (actual SET ROLE anon / authenticated checks) is covered by
backend/scripts/hardening/test_01c_catalog_write_lockdown_runtime.sql, and the post-apply
state by the read-only verify_01c_catalog_write_lockdown.sql.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
WEB_SRC = ROOT / "web" / "src"
HARDENING = BACKEND / "scripts" / "hardening"
DRAFT_01C = HARDENING / "01c_DRAFT_catalog_write_lockdown.sql"
ROLLBACK_01C = HARDENING / "01c_DRAFT_catalog_write_lockdown_rollback.sql"
VERIFY_01C = HARDENING / "verify_01c_catalog_write_lockdown.sql"
RUNTIME_SQL_TEST = HARDENING / "test_01c_catalog_write_lockdown_runtime.sql"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci_cd.yml"

CATALOG_WRITE_PRIVS = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")

pytestmark = pytest.mark.unit

# Directories that do not run inside the deployed API / web app.
NON_RUNTIME_DIRS = {
    "tests",
    "scripts",
    "evaluation",
    "__pycache__",
    "node_modules",
    ".next",
    ".next-e2e",
}

# Known REST write to a catalog table from runtime code: SupabaseBookDataPort.upsert_embedding.
# Under production RLS (book_embeddings is SELECT-only for anon) it fails with 42501 and the
# contribution flow falls back to scripts/backfill_embeddings.py. It must NOT be "fixed" by adding
# an anon/authenticated write policy on book_embeddings (that would let anyone poison RAG vectors).
KNOWN_REST_CATALOG_WRITES = {
    ("backend/infrastructure/persistence/supabase_adapters.py", "book_embeddings", "upsert"),
}

REST_WRITE_RE = re.compile(
    r"""\.(?:table|from_?)\(\s*['"`](books|book_embeddings)['"`]\s*\)\s*\.\s*(insert|upsert|update|delete)\b""",
    re.MULTILINE,
)


def _runtime_sources():
    for base, patterns in ((BACKEND, ("*.py",)), (WEB_SRC, ("*.ts", "*.tsx", "*.js", "*.jsx"))):
        for pattern in patterns:
            for path in base.rglob(pattern):
                rel_parts = path.relative_to(ROOT).parts
                if NON_RUNTIME_DIRS.intersection(rel_parts):
                    continue
                yield path


def _sql_statements(path: Path) -> str:
    """SQL text without -- comments, whitespace-normalised and upper-cased."""
    text = "\n".join(
        line.split("--", 1)[0] for line in path.read_text(encoding="utf-8").splitlines()
    )
    return re.sub(r"\s+", " ", text).upper()


# ── 1. Contribution path: definer RPC with the reader's JWT, never a table write ───────────────


class _FakeQuery:
    def __init__(self, log, name):
        self._log, self._name = log, name

    def __getattr__(self, attr):
        def call(*args, **kwargs):
            self._log.append((self._name, attr, args))
            return self

        return call


class _FakeClient:
    def __init__(self, log):
        self._log = log
        outer = self

        class _Postgrest:
            def auth(self, token):
                outer._log.append(("postgrest", "auth", (token,)))

        self.postgrest = _Postgrest()

    def table(self, name):
        self._log.append(("table", name, ()))
        return _FakeQuery(self._log, f"table:{name}")

    def rpc(self, fn, params):
        self._log.append(("rpc", fn, (params,)))
        return _FakeQuery(self._log, f"rpc:{fn}")


BOOK = {
    "isbn13": "9781234567897",
    "title": "A Book",
    "authors": "An Author",
    "categories": "Science",
    "description": "",
    "thumbnail": "",
    "page_count": 120,
    "published_date": "2020",
}


@pytest.fixture
def fake_supabase(monkeypatch):
    import supabase

    log = []
    created = []

    def fake_create_client(url, key):
        created.append(key)
        return _FakeClient(log)

    monkeypatch.setattr(supabase, "create_client", fake_create_client)
    return log, created


def test_add_book_calls_definer_rpc_with_reader_jwt_and_never_writes_the_table(fake_supabase):
    from backend.config import Config
    from backend.infrastructure.persistence.supabase_adapters import SupabaseBookDataPort

    log, created = fake_supabase
    port = SupabaseBookDataPort(supabase_client=object())

    assert port.add_book(dict(BOOK), user_token="reader-jwt") is True

    assert created == [Config.SUPABASE_ANON_KEY], (
        "contribution must use the public key, never an elevated one"
    )
    assert ("postgrest", "auth", ("reader-jwt",)) in log, (
        "RPC must run under the reader's JWT (auth.uid())"
    )
    rpcs = [entry for entry in log if entry[0] == "rpc"]
    assert [r[1] for r in rpcs] == ["add_catalog_book"]
    assert rpcs[0][2][0]["p_isbn13"] == BOOK["isbn13"]
    assert not [entry for entry in log if entry[0] == "table"], (
        "books must not be written over REST"
    )


def test_add_book_without_reader_token_writes_nothing(fake_supabase):
    from backend.infrastructure.persistence.supabase_adapters import SupabaseBookDataPort

    log, created = fake_supabase
    port = SupabaseBookDataPort(supabase_client=object())

    assert port.add_book(dict(BOOK), user_token=None) is False
    assert created == [] and log == []


def test_contribution_survives_a_denied_embedding_upsert():
    """Production RLS denies the anon REST upsert on book_embeddings (42501). The book must still
    be created and persisted; only the vector is deferred to the backfill job."""
    from backend.application.use_cases.catalog_contributions import AddCatalogBookUseCase
    from backend.infrastructure.ml.recommender import BookRecommender

    class Port:
        def add_book(self, book, user_token=None):
            return True

    class DeniedEmbeddings:
        def is_configured(self):
            return True

        def generate_canonical_text(self, book):
            return "text"

        def generate_embedding(self, text):
            return [0.1] * 8

        def generate_content_hash(self, text):
            return "hash"

        def upsert_embedding(self, *args, **kwargs):
            raise PermissionError(
                'new row violates row-level security policy for table "book_embeddings" (42501)'
            )

    rec = BookRecommender()
    rec.load_from_dicts(
        [
            {
                "isbn13": "9780000000101",
                "title": "Atomic Habits",
                "authors": "James Clear",
                "categories": "Self-Help",
                "description": "Habits.",
                "average_rating": 4.5,
                "ratings_count": 100,
                "published_date": "2018",
                "page_count": 320,
            },
            {
                "isbn13": "9780000000102",
                "title": "Deep Work",
                "authors": "Cal Newport",
                "categories": "Business",
                "description": "Focus.",
                "average_rating": 4.2,
                "ratings_count": 80,
                "published_date": "2016",
                "page_count": 296,
            },
        ]
    )
    rec.fit()
    uc = AddCatalogBookUseCase(
        rec, Port(), embedding_service=DeniedEmbeddings(), run_background=lambda fn: fn()
    )

    book, created, persisted = uc.execute(
        "user-1", {"title": "New Book", "authors": "Someone"}, user_token="jwt"
    )

    assert created is True and persisted is True
    assert rec.get_book_by_isbn(book["isbn13"]) is not None


# ── 2. Static guards over runtime code ──────────────────────────────────────────────────────────


def test_runtime_code_has_no_new_rest_writes_to_catalog_tables():
    found = set()
    for path in _runtime_sources():
        for match in REST_WRITE_RE.finditer(path.read_text(encoding="utf-8", errors="ignore")):
            found.add((path.relative_to(ROOT).as_posix(), match.group(1), match.group(2)))

    unexpected = found - KNOWN_REST_CATALOG_WRITES
    assert not unexpected, (
        f"Runtime code writes catalog tables over REST: {sorted(unexpected)}. Clients must go through "
        "add_catalog_book (books) or a server-side path (book_embeddings); do not add client write policies."
    )
    # Keep the allowlist honest: drop an entry once its write path is removed.
    assert found == KNOWN_REST_CATALOG_WRITES, (
        f"stale allowlist entries: {sorted(KNOWN_REST_CATALOG_WRITES - found)}"
    )


def test_web_app_never_reads_or_writes_book_embeddings():
    """book_embeddings SELECT is needed by the backend (vector RPCs), not by the browser/web app."""
    offenders = [
        p.relative_to(ROOT).as_posix()
        for p in _runtime_sources()
        if p.is_relative_to(WEB_SRC)
        and re.search(
            r"book_embeddings|match_(query|book)_embeddings",
            p.read_text(encoding="utf-8", errors="ignore"),
        )
    ]
    assert offenders == []


def test_only_the_offline_ingestion_script_reads_a_service_role_key():
    pattern = re.compile(r"SERVICE_ROLE_KEY|SUPABASE_SECRET_KEY")
    users = sorted(
        p.relative_to(ROOT).as_posix()
        for p in BACKEND.rglob("*.py")
        if "tests" not in p.relative_to(BACKEND).parts
        and pattern.search(p.read_text(encoding="utf-8", errors="ignore"))
    )
    assert users == ["backend/scripts/upload_books_to_supabase.py"]
    for web_file in _runtime_sources():
        if web_file.is_relative_to(WEB_SRC):
            assert not re.search(
                r"service_role|SERVICE_ROLE", web_file.read_text(encoding="utf-8", errors="ignore")
            ), web_file


# ── 3. Hardening draft 01c: closes client writes, keeps every read path ────────────────────────


def _revoke_targets(sql: str):
    """(privileges, tables, grantees) for every REVOKE ... ON [TABLE] ... FROM ... statement."""
    for m in re.finditer(r"REVOKE ([A-Z, ]+?) ON (?:TABLE )?([A-Z_., ]+?) FROM ([A-Z_, ]+?);", sql):
        yield (
            {p.strip() for p in m.group(1).split(",")},
            {t.strip() for t in m.group(2).split(",")},
            {g.strip() for g in m.group(3).split(",")},
        )


def test_01c_drops_the_permissive_books_write_policies():
    sql = _sql_statements(DRAFT_01C)
    assert 'DROP POLICY IF EXISTS "PYTHON_EKLEME_IZNI" ON PUBLIC.BOOKS' in sql
    assert 'DROP POLICY IF EXISTS "PYTHON_GUNCELLEME_IZNI" ON PUBLIC.BOOKS' in sql


def test_01c_revokes_every_client_write_privilege_on_both_catalog_tables():
    sql = _sql_statements(DRAFT_01C)
    covered = {
        (priv, table, grantee)
        for privs, tables, grantees in _revoke_targets(sql)
        for priv in privs
        for table in tables
        for grantee in grantees
    }
    for table in ("PUBLIC.BOOKS", "PUBLIC.BOOK_EMBEDDINGS"):
        for grantee in ("ANON", "AUTHENTICATED", "PUBLIC"):
            for priv in CATALOG_WRITE_PRIVS:
                assert (priv, table, grantee) in covered, (priv, table, grantee)


def test_01c_is_scoped_to_the_catalog_tables_only():
    sql = _sql_statements(DRAFT_01C)
    for privs, tables, grantees in _revoke_targets(sql):
        assert tables <= {"PUBLIC.BOOKS", "PUBLIC.BOOK_EMBEDDINGS"}, tables
        assert "SELECT" not in privs and "ALL" not in privs, privs
        assert "SERVICE_ROLE" not in grantees
    for other in (
        "FAVORITES",
        "USER_ACTIVITIES",
        "USER_INTERACTIONS",
        "USER_PROFILES",
        "TEST_HALFVEC",
    ):
        assert f"PUBLIC.{other}" not in sql, other


def test_01c_keeps_catalog_and_rag_read_paths():
    sql = _sql_statements(DRAFT_01C)
    assert (
        "GRANT SELECT ON TABLE PUBLIC.BOOKS, PUBLIC.BOOK_EMBEDDINGS TO ANON, AUTHENTICATED" in sql
    )
    for forbidden in (
        "REVOKE SELECT",
        'DROP POLICY IF EXISTS "BOOKS ARE VIEWABLE BY EVERYONE"',
        'DROP POLICY IF EXISTS "EMBEDDINGS ARE READABLE BY EVERYONE"',
        # Things the change must not touch at all.
        "ADD_CATALOG_BOOK",
        "MATCH_QUERY_EMBEDDINGS",
        "MATCH_BOOK_EMBEDDINGS",
        "ON FUNCTION",
        "ALTER FUNCTION",
        "ALTER TABLE",
        "OWNER TO",
        "ROW LEVEL SECURITY",
        "SERVICE_ROLE",
        "CREATE POLICY",
    ):
        assert forbidden not in sql, forbidden


def test_01c_never_grants_client_writes_on_catalog_tables():
    for path in (DRAFT_01C,):
        sql = _sql_statements(path)
        grant_writes = re.compile(
            r"GRANT [^;]*\b(INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER|ALL)\b[^;]* ON (TABLE )?PUBLIC\.(BOOKS|BOOK_EMBEDDINGS)\b"
        )
        assert not grant_writes.search(sql), path


def test_01c_is_atomic_lock_bounded_and_fails_closed():
    sql = _sql_statements(DRAFT_01C)
    assert sql.strip().startswith("BEGIN;") and sql.strip().endswith("COMMIT;")
    assert "SET LOCAL LOCK_TIMEOUT" in sql and "SET LOCAL STATEMENT_TIMEOUT" in sql
    # In-transaction verification aborts the whole change if a write privilege survives.
    assert (
        "HAS_TABLE_PRIVILEGE" in sql
        and "HAS_ANY_COLUMN_PRIVILEGE" in sql
        and "RAISE EXCEPTION" in sql
    )


def test_01c_rollback_never_reopens_the_hole():
    sql = _sql_statements(ROLLBACK_01C)
    assert sql.strip().startswith("BEGIN;") and sql.strip().endswith("COMMIT;")
    assert "CREATE POLICY" not in sql, "rollback must not re-create the permissive write policies"
    assert "TRUNCATE" not in sql, "TRUNCATE bypasses RLS and is never given back"
    assert "SERVICE_ROLE" not in sql and "ADD_CATALOG_BOOK" not in sql


def test_verify_01c_is_read_only_and_covers_the_contract():
    sql = _sql_statements(VERIFY_01C)
    assert sql.strip().startswith("BEGIN READ ONLY;") and sql.strip().endswith("ROLLBACK;")
    for statement in (
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "GRANT ",
        "REVOKE ",
        "CREATE ",
        "ALTER ",
        "DROP ",
        "COMMIT",
    ):
        assert not re.search(rf"(^|;)\s*{statement}", sql), statement
    for needle in (
        "HAS_TABLE_PRIVILEGE",
        "HAS_ANY_COLUMN_PRIVILEGE",
        "ACLEXPLODE",
        "RELFORCEROWSECURITY",
        "PROSECDEF",
        "ADD_CATALOG_BOOK",
        "MATCH_QUERY_EMBEDDINGS",
        "'OVERALL'",
        *(f"('{p}')" for p in CATALOG_WRITE_PRIVS),
    ):
        assert needle in sql, needle


def test_ci_runs_the_01c_runtime_test_and_gates_on_verification():
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "backend/scripts/hardening/test_01c_catalog_write_lockdown_runtime.sql" in ci
    assert "backend/scripts/hardening/verify_01c_catalog_write_lockdown.sql" in ci
    assert "|FAIL$" in ci and "^OVERALL|.*|PASS$" in ci


def test_add_catalog_book_stays_authenticated_only_and_definer():
    sql = _sql_statements(BACKEND / "scripts" / "15_reader_catalog_contributions.sql")
    assert "SECURITY DEFINER" in sql and "SET SEARCH_PATH = PUBLIC, PG_TEMP" in sql
    assert "ON CONFLICT (ISBN13) DO NOTHING" in sql, (
        "contributions must never overwrite catalog rows"
    )
    assert "FROM PUBLIC;" in sql and "FROM ANON;" in sql and "TO AUTHENTICATED;" in sql


def test_runtime_sql_test_covers_the_lockdown_contract():
    sql = _sql_statements(RUNTIME_SQL_TEST)
    for needle in (
        "SET ROLE ANON",
        "SET ROLE AUTHENTICATED",
        "INSERT INTO PUBLIC.BOOKS",
        "UPDATE PUBLIC.BOOKS",
        "DELETE FROM PUBLIC.BOOKS",
        "INSERT INTO PUBLIC.BOOK_EMBEDDINGS",
        "PUBLIC.ADD_CATALOG_BOOK(",
        "PUBLIC.MATCH_QUERY_EMBEDDINGS(",
        "PUBLIC.MATCH_BOOK_EMBEDDINGS(",
        "RELFORCEROWSECURITY",
        "'REFERENCES'",
        "'TRIGGER'",
        "HAS_ANY_COLUMN_PRIVILEGE",
        r"\I BACKEND/SCRIPTS/HARDENING/01C_DRAFT_CATALOG_WRITE_LOCKDOWN.SQL",
        r"\I BACKEND/SCRIPTS/HARDENING/01C_DRAFT_CATALOG_WRITE_LOCKDOWN_ROLLBACK.SQL",
    ):
        assert needle in sql, needle
    assert "01B_DRAFT" not in sql, "the runtime test must exercise 01c, not the bundled 01b draft"


def test_runtime_sql_test_confirms_the_second_application_explicitly():
    sql = _sql_statements(RUNTIME_SQL_TEST)
    forward = r"\I BACKEND/SCRIPTS/HARDENING/01C_DRAFT_CATALOG_WRITE_LOCKDOWN.SQL"
    step2, step3 = sql.index(">> STEP 2 OK"), sql.index(">> STEP 3 OK")
    # Two applications before the STEP 2 confirmation, and the snapshot taken between them.
    first = sql.index(forward)
    snapshot = sql.index("CREATE TEMP TABLE T01C_AFTER_FIRST_APPLY")
    second = sql.index(forward, first + 1)
    assert first < snapshot < second < step2 < step3
    assert sql.count(forward) == 3, "forward x2 (idempotency) + re-forward after rollback"
    for needle in ("ACLEXPLODE(ATT.ATTACL)", "PG_POLICIES", "RELFORCEROWSECURITY", "EXCEPT"):
        assert needle in sql[snapshot:step2], needle


def test_ci_runs_01c_as_a_non_superuser_non_bypassrls_table_owner():
    """verify_01c check 64 passes through rolsuper when the CI postgres superuser owns everything.
    CI must also run the 01c test + verify as an owner that is neither superuser nor BYPASSRLS."""
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"CREATE ROLE catalog_owner LOGIN NOSUPERUSER NOBYPASSRLS\b", ci)
    assert "CREATE DATABASE libris_01c_owner OWNER catalog_owner" in ci
    owner_psql = '"psql -v ON_ERROR_STOP=1 -h localhost -U catalog_owner -d libris_01c_owner"'
    assert f"OWNER_PSQL={owner_psql}" in ci
    owner_part = ci[ci.index("OWNER_PSQL=") :]
    for needle in (
        "$OWNER_PSQL -f backend/scripts/hardening/test_01c_catalog_write_lockdown_runtime.sql",
        "-f backend/scripts/hardening/verify_01c_catalog_write_lockdown.sql | tee /tmp/verify_01c_owner.txt",
        "grep -q '|FAIL$' /tmp/verify_01c_owner.txt",
        "grep -q '^OVERALL|.*|PASS$' /tmp/verify_01c_owner.txt",
        "p.proowner = c.relowner",
        "NOT r.rolsuper AND NOT r.rolbypassrls",
    ):
        assert needle in owner_part, needle
