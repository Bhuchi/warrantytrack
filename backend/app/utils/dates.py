"""Date helpers.

Small enough to live here rather than pull in a dependency: the one thing we
need is "add N calendar months", and getting it to agree with the frontend
matters more than getting it from a library.
"""

from __future__ import annotations

from datetime import date, timedelta


def add_months(start: date, months: int) -> date:
    """`start` plus N calendar months, matching JavaScript's `setMonth`.

    The Add Asset form already shows the user when their warranty will end,
    computed in the browser with `Date.setMonth`
    (frontend/src/features/add-asset/draft.ts). This is the value we then save,
    so the two have to agree — otherwise the form previews one date and the
    asset detail screen shows another.

    That rules out `dateutil.relativedelta`, which *clamps* an impossible day
    to the end of the month (31 Jan + 1 month → 28 Feb). JavaScript instead
    *rolls over* into the next month (31 Jan + 1 month → 3 Mar). Building the
    date as "first of the target month, plus (day - 1) days" reproduces the
    rollover exactly, and needs no dependency to do it.

    >>> add_months(date(2025, 3, 1), 36)
    datetime.date(2028, 3, 1)
    >>> add_months(date(2025, 1, 31), 1)   # February has no 31st
    datetime.date(2025, 3, 3)
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1

    return date(year, month, 1) + timedelta(days=start.day - 1)
