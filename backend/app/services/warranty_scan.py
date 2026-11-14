"""The scheduled warranty-expiry scan (CLOUDAPPG5-98).

Run once a day by EventBridge Scheduler (see scripts/scan_warranties.py). For
every warranty about to lapse it writes a `notifications` row per person who
should know, then emails each of them one digest.

Three things this gets right, because each has a way of going wrong quietly:

**It is a scheduled task, not an in-process timer.** With more than one Fargate
task running, an in-process scheduler fires on every task and sends duplicate
emails (docs/architecture.md). The entrypoint takes a Postgres advisory lock so
only one run proceeds even if the scheduler double-fires.

**It reminds at the person's chosen days, once each.** Settings →
Notifications picks reminder days from 60 / 30 / 14 / 7 / 1 (default 30, 14,
7; GitHub #82). A reminder goes out when the warranty *crosses* one of them,
not only on that exact day, so a missed scheduler run still reminds the next
day. Each crossed threshold reminds once; the existing rows are the record.
Turning Email off writes the row but leaves it out of the email; turning
In-app off still writes the row (it is the record) and the bell list hides it.

**The in-app row is the record; the email is the nudge.** If SES fails the row
still exists, so the bell menu is right even when mail is broken.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.membership import Membership, MembershipRole
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.models.warranty import Warranty
from app.models.notification_settings import REMIND_DAY_OPTIONS
from app.services import email as email_service
from app.services import notification_settings
from app.services.warranty import compute_status, soon_cutoff

logger = logging.getLogger(__name__)

#: Don't tell the same person an asset has expired again within this many days.
RENOTIFY_AFTER_DAYS = 30

#: How far ahead the scan looks: the largest reminder day anyone can choose.
#: Each person's own reminder days then decide whether they hear about it.
SCAN_WINDOW_DAYS = max(REMIND_DAY_OPTIONS)

#: How far back to look for warranties that have just lapsed. Bounded so the
#: first ever run does not email years of history.
EXPIRED_LOOKBACK_DAYS = 7


@dataclass
class ScanResult:
    """What one run did, for the log and for the tests."""

    notifications_created: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    skipped_as_duplicate: int = 0
    skipped_by_settings: int = 0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"{self.notifications_created} notification(s), "
            f"{self.emails_sent} email(s) sent, "
            f"{self.emails_failed} failed, "
            f"{self.skipped_as_duplicate} skipped as recently notified, "
            f"{self.skipped_by_settings} not yet due by the person's reminder days"
        )


def _title(asset_name: str, end_date: date, today: date) -> tuple[NotificationType, str]:
    """The notification type and the sentence the bell menu shows.

    Written once here and stored on the row: the title is rendered as written,
    so renaming or deleting the asset later does not rewrite history in the
    bell menu (see the Notification model).
    """
    days_left = (end_date - today).days
    if days_left < 0:
        lapsed = abs(days_left)
        when = "yesterday" if lapsed == 1 else f"{lapsed} days ago"
        return NotificationType.warranty_expired, f"{asset_name} warranty expired {when}"
    if days_left == 0:
        return NotificationType.warranty_expiring, f"{asset_name} warranty expires today"
    unit = "day" if days_left == 1 else "days"
    return (
        NotificationType.warranty_expiring,
        f"{asset_name} warranty expires in {days_left} {unit}",
    )


def _recipients(db: Session, asset: Asset) -> list[User]:
    """Who hears about this asset.

    Owners and admins, because managing warranties is their job, plus the
    employee the asset is assigned to, because it is the thing they use. An
    employee is not told about assets that are not theirs — the same rule the
    rest of the API applies.
    """
    managers = db.scalars(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.workspace_id == asset.workspace_id,
            Membership.role.in_([MembershipRole.owner, MembershipRole.admin]),
        )
    ).all()

    people = {user.id: user for user in managers}

    if asset.assigned_to_user_id is not None:
        assignee = db.get(User, asset.assigned_to_user_id)
        if assignee is not None:
            people.setdefault(assignee.id, assignee)

    return list(people.values())


def _notified_recently(
    db: Session,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    notification_type: NotificationType,
) -> bool:
    """Whether this person was already told about this asset lately.

    Keyed on (user, asset, type) within a window rather than "ever": a warranty
    renewed for another three years should be able to warn again when it next
    comes due, which "ever" would silence forever.

    The window is measured against the **real clock**, not the scan's `today`.
    "Have we already emailed this person" is a question about what actually
    happened, and `notifications.created_at` records the real moment. Taking
    the window from a simulated `--today` instead compared a pretend date with
    a real timestamp, which silently let `--today` rewind the cooldown and
    write a second copy of a notification already sent.
    """
    since = datetime.now(timezone.utc) - timedelta(days=RENOTIFY_AFTER_DAYS)
    existing = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.asset_id == asset_id,
            Notification.type == notification_type,
            Notification.created_at >= since,
        )
    ).first()
    return existing is not None


def _threshold_to_remind(remind_days: tuple[int, ...], days_left: int) -> int | None:
    """The smallest chosen reminder day this warranty has crossed, if any.

    `days_left <= t` rather than `== t`: if yesterday's run was missed, today's
    still reminds. The smallest crossed one is what matters, because a reminder
    for it also covers every larger one.
    """
    crossed = [t for t in remind_days if days_left <= t]
    return min(crossed) if crossed else None


def _reminded_since_crossing(
    db: Session, user_id: uuid.UUID, asset_id: uuid.UUID, days_since_crossing: int
) -> bool:
    """Whether this person got an expiring reminder for this asset since the
    warranty crossed the threshold now in force.

    No extra column: the reminder was sent if a row exists from on or after the
    day of crossing. Like `_notified_recently`, measured on the **real clock**
    (today's real date minus how many days ago the crossing was), never the
    scan's simulated `today`, so `--today` cannot rewind it. Whole days, not
    24-hour spans, so a run at 09:00 still sees yesterday's 08:00 row.
    """
    crossing_day = datetime.now(timezone.utc).date() - timedelta(days=days_since_crossing)
    since = datetime.combine(crossing_day, time.min, tzinfo=timezone.utc)
    existing = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.asset_id == asset_id,
            Notification.type == NotificationType.warranty_expiring,
            Notification.created_at >= since,
        )
    ).first()
    return existing is not None


def _due_warranties(db: Session, today: date, days: int) -> list[tuple[Asset, Warranty]]:
    """Warranties lapsing within `days`, plus those that just lapsed."""
    rows = db.execute(
        select(Asset, Warranty)
        .join(Warranty, Warranty.asset_id == Asset.id)
        .where(
            Warranty.end_date >= today - timedelta(days=EXPIRED_LOOKBACK_DAYS),
            # The same boundary the dashboard and the status rule use, so
            # "expiring soon" means one thing across the whole application.
            Warranty.end_date <= soon_cutoff(today, days),
        )
        .order_by(Warranty.end_date)
    ).all()
    return [(asset, warranty) for asset, warranty in rows]


def scan(
    db: Session, today: date | None = None, days: int | None = None
) -> ScanResult:
    """Create the notifications due today and email them. Commits its own work.

    Across every workspace on purpose: this is a scheduled job, not a request,
    so there is no caller whose tenant to scope to. Each row it writes still
    carries the workspace the asset belongs to.
    """
    today = today or datetime.now(timezone.utc).date()
    days = SCAN_WINDOW_DAYS if days is None else days
    result = ScanResult()
    settings_cache: dict[uuid.UUID, notification_settings.Settings] = {}

    # Built up per person so everyone gets one digest instead of one email per
    # asset. A manager with forty assets lapsing should not get forty emails.
    digests: dict[uuid.UUID, tuple[User, list[str]]] = {}

    for asset, warranty in _due_warranties(db, today, days):
        notification_type, title = _title(asset.name, warranty.end_date, today)

        days_left = (warranty.end_date - today).days

        for user in _recipients(db, asset):
            if user.id not in settings_cache:
                settings_cache[user.id] = notification_settings.for_user(db, user.id)
            prefs = settings_cache[user.id]

            if notification_type is NotificationType.warranty_expired:
                # Unchanged by reminder days: one "expired" alert, always.
                if _notified_recently(db, user.id, asset.id, notification_type):
                    result.skipped_as_duplicate += 1
                    continue
            else:
                threshold = _threshold_to_remind(prefs.remind_days, days_left)
                if threshold is None:
                    result.skipped_by_settings += 1
                    continue
                if _reminded_since_crossing(db, user.id, asset.id, threshold - days_left):
                    result.skipped_as_duplicate += 1
                    continue

            db.add(
                Notification(
                    workspace_id=asset.workspace_id,
                    user_id=user.id,
                    asset_id=asset.id,
                    type=notification_type,
                    title=title,
                    body=(
                        f"Serial number {asset.serial_number}. "
                        f"Cover ends {warranty.end_date.isoformat()}"
                        + (f", provider {warranty.provider}." if warranty.provider else ".")
                    ),
                )
            )
            result.notifications_created += 1
            if prefs.email_enabled:
                digests.setdefault(user.id, (user, []))[1].append(title)

    # Committed before the emails go out: if SES is down, or this task is
    # killed mid-send, the bell menu is still correct and the next run skips
    # these as recently notified rather than writing them again.
    db.commit()

    for user, titles in digests.values():
        outcome = email_service.send(
            to=user.email,
            subject=_subject(len(titles)),
            body=_body(user.display_name or user.email, titles),
        )
        if outcome.sent:
            result.emails_sent += 1
        else:
            result.emails_failed += 1
            if outcome.error:
                result.errors.append(f"{user.email}: {outcome.error}")

    logger.info("Warranty scan for %s: %s", today.isoformat(), result)
    return result


def _subject(count: int) -> str:
    if count == 1:
        return "A warranty needs your attention"
    return f"{count} warranties need your attention"


def _body(name: str, titles: list[str]) -> str:
    lines = "\n".join(f"  - {title}" for title in titles)
    return (
        f"Hello {name},\n\n"
        "These warranties are expiring or have just expired:\n\n"
        f"{lines}\n\n"
        "Open WarrantyTrack to see the assets and their receipts.\n"
    )


def status_of(warranty: Warranty, today: date | None = None) -> str:
    """Convenience for logging a row's status with the shared rule."""
    return compute_status(warranty.end_date, today).value
