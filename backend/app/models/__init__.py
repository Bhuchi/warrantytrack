"""Every model must be imported here so Alembic can see it."""

from app.models.asset import Asset, AssetCondition
from app.models.catalog import Category, Department, Location, Vendor
from app.models.document import (
    AssetDocument,
    Document,
    DocumentKind,
    DocumentStatus,
)
from app.models.membership import Membership, MembershipRole
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.models.warranty import Warranty
from app.models.workspace import Workspace, WorkspaceType
from app.models.workspace_invite import WorkspaceInvite

__all__ = [
    "Asset",
    "AssetCondition",
    "AssetDocument",
    "Category",
    "Department",
    "Document",
    "DocumentKind",
    "DocumentStatus",
    "Location",
    "Membership",
    "MembershipRole",
    "Notification",
    "NotificationType",
    "User",
    "Vendor",
    "Warranty",
    "Workspace",
    "WorkspaceType",
    "WorkspaceInvite",
]
