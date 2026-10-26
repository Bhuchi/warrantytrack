"""Shared request dependencies for routes.

Authentication (Amazon Cognito) is Chaitawat's foundation work. Until the real
token-verification dependency lands, every leg develops against a STUB that
returns a fixed dev workspace/user — the same IDs that `scripts/seed_dev.py`
inserts.

API-First in practice: routes depend on `get_current_workspace` /
`get_current_user` by NAME. When the real auth arrives, only the *body* of
these functions changes (verify the JWT -> look up the membership); every route
keeps working untouched. That is why a route never reads a token itself.
"""

from __future__ import annotations

import uuid

from app.core.config import settings

# Deterministic IDs so the stub and the seed script always agree on "who".
DEV_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _forbid_stub_in_prod() -> None:
    # A loud failure is better than silently serving one hard-coded user in prod.
    if settings.environment == "production":
        raise RuntimeError(
            "Auth stub is active in production. Replace app.api.deps with the "
            "real Cognito dependency before deploying."
        )


def get_current_workspace() -> uuid.UUID:
    """STUB — the workspace the request acts in.

    Real version: read `workspace_id` from the verified token / active
    membership. Signature stays `() -> uuid.UUID`, so routes don't change.
    """
    _forbid_stub_in_prod()
    return DEV_WORKSPACE_ID


def get_current_user() -> uuid.UUID:
    """STUB — the signed-in user. Real version: derive from Cognito `sub`."""
    _forbid_stub_in_prod()
    return DEV_USER_ID
