"""Insert sample workspace/user/notification rows for local development.

Run against the running stack (idempotent — safe to run more than once):

    docker compose exec backend python -m scripts.seed_dev

The fixed IDs are test/sample data. Real requests still need a Cognito token
whose subject matches a local user, so these rows are not signed-in by default.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.deps import DEV_USER_ID, DEV_WORKSPACE_ID
from app.db.session import SessionLocal
from app.models.membership import Membership, MembershipRole
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType


def seed() -> None:
    db = SessionLocal()
    try:
        if db.get(Workspace, DEV_WORKSPACE_ID) is None:
            db.add(
                Workspace(
                    id=DEV_WORKSPACE_ID, name="Dev Workspace", type=WorkspaceType.personal
                )
            )
        if db.get(User, DEV_USER_ID) is None:
            db.add(
                User(
                    id=DEV_USER_ID,
                    cognito_sub="dev-sub",
                    email="dev@warrantytrack.local",
                    display_name="Dev User",
                )
            )
        db.flush()

        membership = (
            db.query(Membership)
            .filter_by(user_id=DEV_USER_ID, workspace_id=DEV_WORKSPACE_ID)
            .first()
        )
        if membership is None:
            db.add(
                Membership(
                    user_id=DEV_USER_ID,
                    workspace_id=DEV_WORKSPACE_ID,
                    role=MembershipRole.owner,
                )
            )

        already = (
            db.query(Notification)
            .filter_by(workspace_id=DEV_WORKSPACE_ID, user_id=DEV_USER_ID)
            .first()
        )
        if already is None:
            now = datetime.now(timezone.utc)
            db.add_all(
                [
                    Notification(
                        workspace_id=DEV_WORKSPACE_ID,
                        user_id=DEV_USER_ID,
                        type=NotificationType.warranty_expiring,
                        title="Dell Latitude 5540 warranty expires in 30 days",
                        read=False,
                        created_at=now - timedelta(days=1),
                    ),
                    Notification(
                        workspace_id=DEV_WORKSPACE_ID,
                        user_id=DEV_USER_ID,
                        type=NotificationType.warranty_expired,
                        title="HP E24 monitor warranty has expired",
                        read=False,
                        created_at=now - timedelta(days=3),
                    ),
                    Notification(
                        workspace_id=DEV_WORKSPACE_ID,
                        user_id=DEV_USER_ID,
                        type=NotificationType.asset_assigned,
                        title="MacBook Air M3 was assigned to you",
                        read=True,
                        read_at=now - timedelta(days=5),
                        created_at=now - timedelta(days=6),
                    ),
                ]
            )

        db.commit()
        print("seed: done (workspace, user, membership, 3 notifications)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
