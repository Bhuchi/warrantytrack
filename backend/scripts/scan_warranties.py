"""Entrypoint for the daily warranty-expiry scan (CLOUDAPPG5-98).

Run it:

    docker compose exec backend python -m scripts.scan_warranties
    docker compose exec backend python -m scripts.scan_warranties --today 2026-12-01

On AWS this is a **one-off ECS task started by EventBridge Scheduler**, not a
thread inside the API. docs/architecture.md explains why: with more than one
Fargate task running, an in-process scheduler fires in every task and every
recipient gets duplicate email.

Belt and braces, it also takes a Postgres advisory lock, so a double-fired
schedule or an accidental manual run alongside the scheduled one does not send
twice. The lock is held by the session and released when it closes, including
if the task is killed — nothing to clean up afterwards.

Exit codes: 0 did the work (or another run held the lock), 1 something failed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timezone

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services import warranty_scan

logger = logging.getLogger("scan_warranties")

#: Any constant works as long as every run uses the same one. Advisory locks
#: live in their own namespace, so this cannot collide with a row lock.
_LOCK_KEY = 528_491


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=(
            "Cap on how far ahead to look (default: the largest reminder day, "
            f"{warranty_scan.SCAN_WINDOW_DAYS}). Each person's reminder days still apply."
        ),
    )
    parser.add_argument(
        "--today",
        type=lambda value: date.fromisoformat(value),
        default=None,
        help="Pretend today is this date (YYYY-MM-DD). For testing a run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _parse_args(argv)
    today = args.today or datetime.now(timezone.utc).date()

    db = SessionLocal()
    try:
        # try_ rather than a blocking lock: if another run is in progress there
        # is nothing useful to wait for — it is doing this very work.
        got_lock = db.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}
        ).scalar()
        if not got_lock:
            logger.info("Another warranty scan holds the lock; nothing to do.")
            return 0

        result = warranty_scan.scan(db, today=today, days=args.days)
        logger.info("Done: %s", result)
        for error in result.errors:
            logger.warning("Email problem: %s", error)
        # Email failures are reported, not fatal: the in-app notifications are
        # written and the next run will not duplicate them.
        return 0
    except Exception:
        logger.exception("Warranty scan failed")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
