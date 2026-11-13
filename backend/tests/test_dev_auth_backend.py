"""AUTH_BACKEND=dev: the local stand-in for Cognito, and the guards around it."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import DEV_USER_ID, DEV_WORKSPACE_ID
from app.core.config import Settings, settings
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType


def test_default_is_real_cognito():
    """Forgetting to set AUTH_BACKEND must fail closed, not open."""
    assert Settings.model_fields["auth_backend"].default == "cognito"


def test_production_refuses_to_start_with_dev_auth():
    with pytest.raises(RuntimeError, match="AUTH_BACKEND"):
        Settings(
            environment="production",
            auth_backend="dev",
            # Everything else production-ready, so AUTH_BACKEND is the only reason.
            storage_backend="s3",
            ocr_backend="bedrock",
            email_backend="ses",
            s3_bucket_name="bucket",
        )


def test_dev_mode_needs_no_token(monkeypatch):
    monkeypatch.setattr(settings, "auth_backend", "dev")
    assert deps.get_current_user(credentials=None, db=None) == DEV_USER_ID


def test_cognito_mode_still_rejects_a_missing_token(monkeypatch):
    monkeypatch.setattr(settings, "auth_backend", "cognito")
    with pytest.raises(HTTPException) as caught:
        deps.get_current_user(credentials=None, db=None)
    assert caught.value.status_code == 401


@pytest.fixture
def dev_rows(db: Session) -> None:
    """The rows scripts/seed_dev.py creates, unless this database already has them."""
    if db.get(Workspace, DEV_WORKSPACE_ID) is None:
        db.add(Workspace(id=DEV_WORKSPACE_ID, name="Dev Workspace", type=WorkspaceType.personal))
    if db.get(User, DEV_USER_ID) is None:
        db.add(User(id=DEV_USER_ID, cognito_sub="dev-sub", email="dev@warrantytrack.local"))
    db.flush()
    if db.query(Membership).filter_by(user_id=DEV_USER_ID, workspace_id=DEV_WORKSPACE_ID).first() is None:
        db.add(Membership(user_id=DEV_USER_ID, workspace_id=DEV_WORKSPACE_ID, role=MembershipRole.owner))
        db.flush()


def test_dev_mode_falls_back_to_the_dev_workspace(monkeypatch, db, dev_rows):
    monkeypatch.setattr(settings, "auth_backend", "dev")
    workspace_id = deps.get_current_workspace(workspace_id=None, user_id=DEV_USER_ID, db=db)
    assert workspace_id == DEV_WORKSPACE_ID


def test_dev_mode_still_checks_membership(monkeypatch, db, dev_rows):
    """The bypass skips the token, not the tenant check."""
    monkeypatch.setattr(settings, "auth_backend", "dev")
    with pytest.raises(HTTPException) as caught:
        deps.get_current_workspace(workspace_id=uuid.uuid4(), user_id=DEV_USER_ID, db=db)
    assert caught.value.status_code == 404
