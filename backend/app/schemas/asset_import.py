"""Response shapes for bulk asset import.

These mirror docs/api.md -> Assets -> bulk import exactly. The dry run and the
real run answer with different fields on purpose: a preview reports how many
*would* be created, a commit reports how many *were*.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel


class ImportMode(str, enum.Enum):
    """Which half of the two-step import this call is.

    An enum rather than a boolean so the URL reads as the contract writes it
    (`?mode=validate`), and so a typo is a 422 naming the parameter instead of
    silently committing.
    """

    validate = "validate"
    commit = "commit"


class ImportRowError(BaseModel):
    """One problem, located the way a spreadsheet user thinks.

    `field` is the **column name**, which is also the API field name — the
    word the user fixes in their file and the word the error uses are the
    same.
    """

    row: int
    field: str
    message: str


class ImportValidateResponse(BaseModel):
    """`?mode=validate` — nothing was written."""

    total_rows: int
    valid: int
    errors: list[ImportRowError]


class ImportCommitResponse(BaseModel):
    """`?mode=commit` — the rows that passed were created.

    `errors` is carried here too, though the contract's example omits it: a
    user whose 47 rows imported still needs to know what was wrong with the
    other three, and making them re-run the dry run to find out would be
    unkind.
    """

    created: int
    skipped: int
    errors: list[ImportRowError]
