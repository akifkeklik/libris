"""
Activity inserts must not ask PostgREST to return the row.

Production's public.user_activities has an INSERT policy (auth.uid() = user_id) but no SELECT
policy. PostgREST's default return=representation runs INSERT ... RETURNING, and RLS rejects that
with 42501 when no SELECT policy matches, which is the error production logged. Reproduced on a
local PostgreSQL: RETURNING -> 42501, plain INSERT -> OK. The row is never used, so the adapter
asks for return=minimal.
"""

from unittest.mock import MagicMock

import pytest
from backend.infrastructure.persistence.supabase_adapters import SupabaseInteractionRepository
from postgrest import SyncPostgrestClient
from postgrest.types import ReturnMethod

pytestmark = pytest.mark.unit

PAYLOAD = {"user_id": "u1", "book_id": "9780000000301", "action": "view"}


def test_track_activity_requests_return_minimal():
    client = MagicMock()
    SupabaseInteractionRepository(client).track_activity(PAYLOAD)
    client.table.assert_called_once_with("user_activities")
    client.table.return_value.insert.assert_called_once_with(PAYLOAD, returning=ReturnMethod.minimal)
    client.table.return_value.insert.return_value.execute.assert_called_once()


def test_postgrest_sends_prefer_return_minimal_for_that_call():
    # Real library, no network: only the request is built.
    builder = SyncPostgrestClient("http://postgrest.invalid").from_("user_activities").insert(
        PAYLOAD, returning=ReturnMethod.minimal)
    assert "return=minimal" in builder.headers.get("Prefer", "")
    default = SyncPostgrestClient("http://postgrest.invalid").from_("user_activities").insert(PAYLOAD)
    assert "return=representation" in default.headers.get("Prefer", "")


def test_track_activity_still_raises_on_failure():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("42501")
    with pytest.raises(RuntimeError):
        SupabaseInteractionRepository(client).track_activity(PAYLOAD)
