"""
SupabaseLearningOutcomesRepository must query as the signed-in user.

It used the container's shared client, which carries only the anon key, so in production every
review_items / review_attempts query would run as anon; RLS (auth.uid() = user_id) rejects that.
The other Supabase repositories already attach the request's JWT; this one now does too.
"""

from unittest.mock import MagicMock, patch

import pytest
from backend.infrastructure.persistence.supabase_adapters import SupabaseLearningOutcomesRepository
from flask import Flask, g

pytestmark = pytest.mark.unit


def test_request_with_jwt_gets_a_user_scoped_client():
    shared = MagicMock(name="shared-anon-client")
    repo = SupabaseLearningOutcomesRepository(shared)
    user_client = MagicMock(name="user-client")
    with Flask(__name__).test_request_context(), patch("supabase.create_client", return_value=user_client) as create:
        g.jwt_token = "user-jwt"
        assert repo._get_client() is user_client
    create.assert_called_once()
    user_client.postgrest.auth.assert_called_once_with("user-jwt")


def test_outside_a_request_the_shared_client_is_used():
    shared = MagicMock(name="shared-anon-client")
    assert SupabaseLearningOutcomesRepository(shared)._get_client() is shared


def test_request_without_jwt_does_not_create_a_user_client():
    shared = MagicMock(name="shared-anon-client")
    with Flask(__name__).test_request_context(), patch("supabase.create_client") as create:
        assert SupabaseLearningOutcomesRepository(shared)._get_client() is shared
    create.assert_not_called()
