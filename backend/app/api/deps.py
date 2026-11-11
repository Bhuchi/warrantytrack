"""Request identity, tenant isolation, and workspace role guards."""

from __future__ import annotations

import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.cognito import verify_id_token
from app.core.config import settings
from app.db.session import get_db
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType

bearer = HTTPBearer(auto_error=False)

# Stable sample IDs retained for scripts/seed_dev.py. Runtime auth never uses them.
DEV_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Resolve a verified Cognito subject to a local user and personal tenant."""
    if settings.auth_backend == "dev":
        # Local only (AUTH_BACKEND=dev, refused in production by config.py):
        # every request is the user that scripts/seed_dev.py creates.
        return DEV_USER_ID
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        claims = verify_id_token(credentials.credentials)
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid authentication token") from None
    except (OSError, RuntimeError):
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from None

    user = db.scalar(select(User).where(User.cognito_sub == claims["sub"]))
    if user is not None:
        return user.id

    # Fetch profile data by the verified subject. Never use email from a JWT
    # for account lookup or authorization (architecture Decision 2).
    try:
        profile = boto3.client("cognito-idp", region_name=settings.aws_region).admin_get_user(
            UserPoolId=settings.cognito_user_pool_id, Username=claims["sub"]
        )
    except (BotoCoreError, ClientError):
        raise HTTPException(status_code=503, detail="Account profile unavailable") from None
    attributes = {item["Name"]: item["Value"] for item in profile["UserAttributes"]}
    email = attributes.get("email")
    if attributes.get("sub") != claims["sub"] or not email:
        raise HTTPException(status_code=401, detail="Account profile invalid")
    user = User(cognito_sub=claims["sub"], email=email, display_name=attributes.get("name"))
    personal = Workspace(name="Personal", type=WorkspaceType.personal)
    try:
        db.add_all([user, personal])
        db.flush()
        db.add(Membership(user_id=user.id, workspace_id=personal.id, role=MembershipRole.owner))
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(User).where(User.cognito_sub == claims["sub"]))
        if existing is None:
            raise
        return existing.id
    return user.id


def get_current_workspace(
    workspace_id: uuid.UUID | None = Header(default=None, alias="X-Workspace-Id"),
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Reject a missing or foreign workspace before a scoped route runs."""
    if workspace_id is None and settings.auth_backend == "dev":
        # The frontend only sends X-Workspace-Id after a Cognito sign-in, so
        # locally fall back to the seeded workspace. Membership is still checked.
        workspace_id = DEV_WORKSPACE_ID
    if workspace_id is None:
        raise HTTPException(status_code=400, detail="X-Workspace-Id is required")
    membership = db.scalar(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == user_id
    ))
    if membership is None:
        raise HTTPException(status_code=404, detail="Not found")
    return workspace_id


def get_current_membership(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
    user_id: uuid.UUID = Depends(get_current_user),
) -> Membership:
    membership = db.scalar(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == user_id
    ))
    if membership is None:
        raise HTTPException(status_code=404, detail="Not found")
    return membership


def employee_scope(membership: Membership) -> uuid.UUID | None:
    return membership.user_id if membership.role is MembershipRole.employee else None


def require_manager(membership: Membership = Depends(get_current_membership)) -> Membership:
    if membership.role is MembershipRole.employee:
        raise HTTPException(status_code=403, detail="Only an owner or admin can do this.")
    return membership
