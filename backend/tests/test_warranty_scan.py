"""The daily warranty-expiry scan (CLOUDAPPG5-98).

What matters here is not that it finds an expiring warranty — that is one date
comparison — but that it tells the right people, exactly once, and that the
in-app notification survives a broken mailer.

Email runs on the `log` backend, so nothing leaves the machine. The two tests
that care about delivery capture `email_service.send` instead.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetCondition
from app.models.membership import Membership, MembershipRole
from app.models.notification import Notification, NotificationType
from app.models.notification_settings import NotificationSettings
from app.models.user import User
from app.models.warranty import Warranty
from app.models.workspace import Workspace, WorkspaceType
from app.services import email as email_service
from app.services import warranty_scan

TODAY = date(2026, 10, 28)


@pytest.fixture
def sent(monkeypatch) -> list[tuple[str, str, str]]:
    """Capture outgoing email instead of logging it."""
    captured: list[tuple[str, str, str]] = []

    def fake_send(to: str, subject: str, body: str):
        captured.append((to, subject, body))
        return email_service.SendResult(sent=True)

    monkeypatch.setattr(warranty_scan.email_service, "send", fake_send)
    return captured


def make_user(db: Session, label: str) -> User:
    user = User(
        cognito_sub=f"{label}-{uuid.uuid4()}",
        email=f"{label}-{uuid.uuid4()}@warrantytrack.local",
        display_name=label.title(),
    )
    db.add(user)
    db.flush()
    return user


def make_workspace(db: Session, **roles: User) -> Workspace:
    """A workspace whose members hold the roles given as keyword arguments."""
    workspace = Workspace(name="Scan Co", type=WorkspaceType.organization)
    db.add(workspace)
    db.flush()
    for role_name, user in roles.items():
        db.add(
            Membership(
                user_id=user.id,
                workspace_id=workspace.id,
                role=MembershipRole[role_name],
            )
        )
    db.flush()
    return workspace


def make_asset(
    db: Session,
    workspace: Workspace,
    *,
    end_offset: int,
    name: str = "Dell Latitude 5540",
    assigned_to: User | None = None,
) -> Asset:
    asset = Asset(
        workspace_id=workspace.id,
        name=name,
        serial_number=f"SN-{uuid.uuid4()}",
        condition=AssetCondition.good,
        purchase_date=TODAY - timedelta(days=500),
        assigned_to_user_id=assigned_to.id if assigned_to else None,
    )
    db.add(asset)
    db.flush()
    db.add(
        Warranty(
            workspace_id=workspace.id,
            asset_id=asset.id,
            end_date=TODAY + timedelta(days=end_offset),
            provider="Dell",
        )
    )
    db.flush()
    return asset


def set_settings(db: Session, user: User, **changes) -> None:
    """Save a person's notification settings over the defaults."""
    row = db.get(NotificationSettings, user.id) or NotificationSettings(user_id=user.id)
    row.in_app_enabled = changes.get("in_app_enabled", True)
    row.email_enabled = changes.get("email_enabled", True)
    row.remind_days = changes.get("remind_days", [30, 14, 7])
    db.add(row)
    db.flush()


def age_notifications(db: Session, user: User, days: int = 1) -> None:
    """Move a person's rows back in real time, as a day passing would."""
    for row in notifications_for(db, user):
        row.created_at = row.created_at - timedelta(days=days)
    db.flush()


def notifications_for(db: Session, user: User) -> list[Notification]:
    return list(
        db.scalars(select(Notification).where(Notification.user_id == user.id)).all()
    )


# --- what gets picked up ---------------------------------------------------


@pytest.mark.parametrize(
    ("end_offset", "expected"),
    [
        (10, 1),      # inside the window
        (30, 1),      # last day of it
        (31, 0),      # outside
        (0, 1),       # expires today
        (-1, 1),      # just lapsed, still worth saying
        (-30, 0),     # long gone; not news, and not emailed on first run
    ],
)
def test_only_warranties_that_are_due_are_reported(
    db: Session, sent, end_offset: int, expected: int
) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=end_offset)

    result = warranty_scan.scan(db, today=TODAY)

    assert result.notifications_created == expected
    assert len(notifications_for(db, owner)) == expected


def test_an_expired_warranty_is_typed_as_expired(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=-1)

    warranty_scan.scan(db, today=TODAY)

    notification = notifications_for(db, owner)[0]
    assert notification.type is NotificationType.warranty_expired
    assert notification.title.endswith("expired yesterday")


def test_the_title_counts_down(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=1, name="Laptop")
    make_asset(db, workspace, end_offset=0, name="Monitor")

    warranty_scan.scan(db, today=TODAY)

    titles = {n.title for n in notifications_for(db, owner)}
    assert "Laptop warranty expires in 1 day" in titles
    assert "Monitor warranty expires today" in titles


def test_the_window_follows_the_persons_reminder_days(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=45)

    # Default reminder days are 30, 14, 7: 45 days out is not due yet.
    assert warranty_scan.scan(db, today=TODAY).notifications_created == 0

    set_settings(db, owner, remind_days=[60])
    assert warranty_scan.scan(db, today=TODAY).notifications_created == 1


# --- who hears about it ----------------------------------------------------


def test_owners_and_admins_are_told(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    admin = make_user(db, "admin")
    workspace = make_workspace(db, owner=owner, admin=admin)
    make_asset(db, workspace, end_offset=10)

    warranty_scan.scan(db, today=TODAY)

    assert len(notifications_for(db, owner)) == 1
    assert len(notifications_for(db, admin)) == 1


def test_the_assigned_employee_is_told_about_their_own_asset(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    employee = make_user(db, "employee")
    workspace = make_workspace(db, owner=owner, employee=employee)
    make_asset(db, workspace, end_offset=10, assigned_to=employee)

    warranty_scan.scan(db, today=TODAY)

    assert len(notifications_for(db, employee)) == 1


def test_an_employee_is_not_told_about_assets_that_are_not_theirs(db: Session, sent) -> None:
    """The same rule the rest of the API applies, applied by the job too."""
    owner = make_user(db, "owner")
    employee = make_user(db, "employee")
    workspace = make_workspace(db, owner=owner, employee=employee)
    make_asset(db, workspace, end_offset=10)  # unassigned

    warranty_scan.scan(db, today=TODAY)

    assert notifications_for(db, employee) == []
    assert len(notifications_for(db, owner)) == 1


def test_one_row_per_person_not_one_shared_row(db: Session, sent) -> None:
    """`read` is per person, so a fan-out cannot be one row."""
    owner = make_user(db, "owner")
    admin = make_user(db, "admin")
    workspace = make_workspace(db, owner=owner, admin=admin)
    asset = make_asset(db, workspace, end_offset=10)

    warranty_scan.scan(db, today=TODAY)

    rows = db.scalars(select(Notification).where(Notification.asset_id == asset.id)).all()
    assert len(rows) == 2
    assert {row.user_id for row in rows} == {owner.id, admin.id}


def test_other_workspaces_are_scanned_too(db: Session, sent) -> None:
    """It is a job, not a request: there is no one tenant to scope to."""
    first_owner = make_user(db, "first")
    second_owner = make_user(db, "second")
    make_asset(db, make_workspace(db, owner=first_owner), end_offset=5)
    make_asset(db, make_workspace(db, owner=second_owner), end_offset=5)

    warranty_scan.scan(db, today=TODAY)

    assert len(notifications_for(db, first_owner)) == 1
    assert len(notifications_for(db, second_owner)) == 1


# --- not nagging -----------------------------------------------------------


def test_a_simulated_date_cannot_rewind_the_cooldown(db: Session, sent) -> None:
    """Regression: `--today` used to re-send notifications already sent.

    The cooldown compared the pretend date with the real `created_at`, so
    `--today 2028-02-20` looked like "nothing sent for over a year" and wrote a
    duplicate on every run. Caught by running the job twice by hand, not by a
    test — which is why this one exists.
    """
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=400)

    far_future = TODAY + timedelta(days=380)
    first = warranty_scan.scan(db, today=far_future)
    second = warranty_scan.scan(db, today=far_future)

    assert first.notifications_created == 1
    assert second.notifications_created == 0
    assert len(notifications_for(db, owner)) == 1


def test_running_twice_in_a_day_does_not_duplicate(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=10)

    first = warranty_scan.scan(db, today=TODAY)
    second = warranty_scan.scan(db, today=TODAY)

    assert first.notifications_created == 1
    assert second.notifications_created == 0
    assert second.skipped_as_duplicate == 1
    assert len(notifications_for(db, owner)) == 1


def test_a_daily_run_does_not_nag_for_thirty_days(db: Session, sent) -> None:
    """The scan runs every day; the person hears once."""
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=25)

    for day in range(10):
        warranty_scan.scan(db, today=TODAY + timedelta(days=day))

    assert len(notifications_for(db, owner)) == 1


def test_a_renewed_warranty_can_warn_again(db: Session, sent) -> None:
    """The reason the de-duplication is a cooldown and not "ever".

    Keyed on (user, asset, type) for all time, a warranty renewed for another
    three years could never warn again — the row from its first expiry would
    silence it permanently.
    """
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    asset = make_asset(db, workspace, end_offset=10)

    warranty_scan.scan(db, today=TODAY)
    assert len(notifications_for(db, owner)) == 1

    # Age the first notification past the cooldown, the way real time would,
    # and renew the warranty so a new expiry comes due.
    first_notification = notifications_for(db, owner)[0]
    first_notification.created_at = datetime.now(timezone.utc) - timedelta(
        days=warranty_scan.RENOTIFY_AFTER_DAYS + 1
    )
    later = TODAY + timedelta(days=warranty_scan.RENOTIFY_AFTER_DAYS + 1)
    asset.warranty.end_date = later + timedelta(days=10)
    db.flush()

    warranty_scan.scan(db, today=later)

    assert len(notifications_for(db, owner)) == 2


def test_the_cooldown_still_holds_for_a_renewed_warranty_warned_recently(
    db: Session, sent
) -> None:
    """Renewing is not a way to get notified twice in the same month."""
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    asset = make_asset(db, workspace, end_offset=10)

    warranty_scan.scan(db, today=TODAY)
    asset.warranty.end_date = TODAY + timedelta(days=20)
    db.flush()
    second = warranty_scan.scan(db, today=TODAY + timedelta(days=2))

    assert second.notifications_created == 0
    assert len(notifications_for(db, owner)) == 1


# --- email -----------------------------------------------------------------


def test_each_person_gets_one_digest_not_one_email_per_asset(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=5, name="Laptop")
    make_asset(db, workspace, end_offset=6, name="Monitor")
    make_asset(db, workspace, end_offset=7, name="Phone")

    result = warranty_scan.scan(db, today=TODAY)

    assert result.notifications_created == 3
    assert result.emails_sent == 1
    assert len(sent) == 1
    to, subject, body = sent[0]
    assert to == owner.email
    assert subject == "3 warranties need your attention"
    for name in ("Laptop", "Monitor", "Phone"):
        assert name in body


def test_a_broken_mailer_still_leaves_the_notification(db: Session, monkeypatch) -> None:
    """The in-app row is the record; the email is only the nudge."""
    monkeypatch.setattr(
        warranty_scan.email_service,
        "send",
        lambda **_: email_service.SendResult(sent=False, error="SES is down"),
    )
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    make_asset(db, workspace, end_offset=10)

    result = warranty_scan.scan(db, today=TODAY)

    assert result.emails_failed == 1
    assert result.errors == [f"{owner.email}: SES is down"]
    # Written and committed before the send was attempted.
    assert len(notifications_for(db, owner)) == 1


# --- reminder days, email and in-app switches (GitHub #82) ------------------


def test_a_daily_run_reminds_once_at_each_chosen_day(db: Session, sent) -> None:
    """Thirty-one daily runs, reminder days 30 and 7: exactly two reminders."""
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    set_settings(db, owner, remind_days=[30, 7])
    make_asset(db, workspace, end_offset=31, name="Laptop")

    for day in range(31):  # days left 31 down to 1
        warranty_scan.scan(db, today=TODAY + timedelta(days=day))
        age_notifications(db, owner)

    titles = sorted(n.title for n in notifications_for(db, owner))
    assert titles == ["Laptop warranty expires in 30 days", "Laptop warranty expires in 7 days"]


def test_nothing_before_the_first_chosen_day(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    set_settings(db, owner, remind_days=[7])
    make_asset(db, workspace, end_offset=20)

    result = warranty_scan.scan(db, today=TODAY)

    assert result.notifications_created == 0
    assert result.skipped_by_settings == 1


def test_a_missed_run_still_reminds_the_next_day(db: Session, sent) -> None:
    """Crossing, not equality: 14 days left was two days ago, nobody was told."""
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    set_settings(db, owner, remind_days=[14])
    make_asset(db, workspace, end_offset=12)

    assert warranty_scan.scan(db, today=TODAY).notifications_created == 1


def test_no_reminder_days_still_says_it_expired(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    set_settings(db, owner, remind_days=[])
    make_asset(db, workspace, end_offset=3, name="Laptop")
    make_asset(db, workspace, end_offset=-1, name="Monitor")

    warranty_scan.scan(db, today=TODAY)

    assert [n.title for n in notifications_for(db, owner)] == ["Monitor warranty expired yesterday"]


def test_email_off_writes_the_row_but_sends_nothing(db: Session, sent) -> None:
    owner = make_user(db, "owner")
    admin = make_user(db, "admin")
    workspace = make_workspace(db, owner=owner, admin=admin)
    set_settings(db, owner, email_enabled=False)
    make_asset(db, workspace, end_offset=10)

    result = warranty_scan.scan(db, today=TODAY)

    assert len(notifications_for(db, owner)) == 1
    assert [to for to, _, _ in sent] == [admin.email]
    assert result.emails_sent == 1


def test_in_app_off_still_writes_the_row(db: Session, sent) -> None:
    """The row is the de-duplication record; the bell list hides it instead."""
    owner = make_user(db, "owner")
    workspace = make_workspace(db, owner=owner)
    set_settings(db, owner, in_app_enabled=False)
    make_asset(db, workspace, end_offset=10)

    warranty_scan.scan(db, today=TODAY)
    second = warranty_scan.scan(db, today=TODAY)

    assert len(notifications_for(db, owner)) == 1
    assert second.skipped_as_duplicate == 1
