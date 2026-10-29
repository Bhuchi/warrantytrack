"""Bulk asset import from a spreadsheet (CLOUDAPPG5-93).

**This module parses and reports. It does not decide what a valid asset is.**
Every rule comes from `AssetCreate` and `asset_validation`, the same pair that
`POST /assets` and Leg B's OCR confirm go through, so a row rejected here would
have been rejected there for the same reason and with the same wording. A
second rule set would drift within a week.

The shape of the work, per docs/api.md:

    mode=validate   parse everything, check everything, write nothing
    mode=commit     the same, then create the rows that passed

Two passes over the same code rather than two code paths: `commit` is
`validate` plus writes, so a dry run cannot promise something the real run
then refuses.

Partial by design. The contract's example answers 50 rows with
`{"created": 47, "skipped": 3}` — three bad rows do not discard forty-seven
good ones. Each row is created inside its own savepoint, so one failure rolls
back only itself.

CSV only for now. `.xlsx` needs `openpyxl`, which is not in requirements.txt,
and a new pin means a rebuild for every teammate — worth doing deliberately
rather than in passing.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field as dataclass_field

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.schemas.asset import AssetCreate
from app.services import asset as asset_service
from app.services import asset_validation
from app.services.asset import DuplicateSerialNumber, UnknownDocument
from app.services.asset_validation import AssetValidationError

#: The header a user's file must carry. Named after the API fields, because
#: docs/api.md reports errors as {"field": "serial_number"} — the column the
#: user fixes and the field the error names should be the same word.
#:
#: The three warranty columns flatten `AssetCreate.warranty`: a spreadsheet
#: has no nesting.
COLUMNS = (
    "name",
    "serial_number",
    "condition",
    "purchase_date",
    "price",
    "currency",
    "invoice_number",
    "vendor",
    "category",
    "department",
    "location",
    "storage_note",
    "warranty_provider",
    "warranty_start_date",
    "warranty_duration_months",
)

#: Columns a file must contain. The optional ones may be left out entirely —
#: a user who tracks no departments should not need an empty column for them.
REQUIRED_COLUMNS = (
    "name",
    "serial_number",
    "condition",
    "purchase_date",
    "price",
    "invoice_number",
    "vendor",
    "category",
    "warranty_provider",
    "warranty_start_date",
    "warranty_duration_months",
)

#: Bounded so one request cannot tie up a worker or the database. A few
#: hundred assets is what this product's users have; anything larger wants the
#: background job described in docs/architecture.md.
MAX_ROWS = 1000

#: The first data row of a spreadsheet, counting the header as row 1. Errors
#: quote the number the user sees in their own file, not a zero-based index.
FIRST_DATA_ROW = 2


class ImportError_(Exception):
    """The file itself is unusable — not a row problem, a file problem."""


@dataclass(frozen=True)
class RowError:
    """One problem, located the way a spreadsheet user thinks: row and column."""

    row: int
    field: str
    message: str

    def as_dict(self) -> dict[str, object]:
        return {"row": self.row, "field": self.field, "message": self.message}


@dataclass
class ImportReport:
    total_rows: int = 0
    valid: int = 0
    created: int = 0
    skipped: int = 0
    errors: list[RowError] = dataclass_field(default_factory=list)


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    """Rows as dictionaries, keyed by header.

    `utf-8-sig` because Excel writes a byte-order mark when it saves CSV, and
    a BOM left in place turns the first header into "﻿name", which then
    looks like a missing column to the user who did nothing wrong.

    Raises ImportError_ for anything that makes the file unreadable — a
    file-level problem has no row number to report it against.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportError_(
            "The file is not UTF-8 text. Save it as CSV (UTF-8) and try again."
        ) from error

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ImportError_("The file is empty.")

    headers = {name.strip() for name in reader.fieldnames if name}
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise ImportError_(f"Missing required column(s): {', '.join(missing)}")

    rows = [
        {(key or "").strip(): (value or "").strip() for key, value in row.items()}
        for row in reader
    ]

    if len(rows) > MAX_ROWS:
        raise ImportError_(
            f"{len(rows)} rows is more than the {MAX_ROWS}-row limit for one import."
        )

    return rows


def _to_payload(row: dict[str, str]) -> dict[str, object]:
    """Turn one spreadsheet row into the body `POST /assets` would accept.

    Blank cells are **dropped rather than sent as empty strings**, so Pydantic
    reports "Field required" against the column the user left empty instead of
    a type error about "". A spreadsheet has no way to say "absent" other than
    an empty cell.

    The three warranty columns become the nested object; if all three are
    blank the key is omitted entirely, which produces one clear "warranty is
    required" rather than three confusing sub-errors.
    """
    present = {key: value for key, value in row.items() if value}

    payload: dict[str, object] = {
        key: present[key]
        for key in (
            "name",
            "serial_number",
            "condition",
            "purchase_date",
            "price",
            "currency",
            "invoice_number",
            "storage_note",
        )
        if key in present
    }

    # Names, not ids: a spreadsheet holds "Power Buy". `create_asset` looks
    # each one up in this workspace and creates it if new — the same path the
    # Add Asset form uses.
    for column, api_field in (
        ("vendor", "vendor_name"),
        ("category", "category_name"),
        ("location", "location_name"),
    ):
        if column in present:
            payload[api_field] = present[column]

    warranty = {
        "provider": present.get("warranty_provider"),
        "start_date": present.get("warranty_start_date"),
        "duration_months": present.get("warranty_duration_months"),
    }
    if any(value is not None for value in warranty.values()):
        payload["warranty"] = {
            key: value for key, value in warranty.items() if value is not None
        }

    return payload


#: API field -> the column the user actually has in their file. The service
#: validators talk in API terms (`vendor_id`), because that is what a JSON
#: caller sends; a spreadsheet has one column called `vendor`. Telling someone
#: to fix `vendor_id` when their header says `vendor` is a small cruelty.
_API_FIELD_TO_COLUMN = {
    "vendor_id": "vendor",
    "vendor_name": "vendor",
    "category_id": "category",
    "category_name": "category",
    "location_id": "location",
    "location_name": "location",
    "department_id": "department",
}


def _column_for_field(api_field: str) -> str:
    """The spreadsheet column a service-level error belongs to."""
    return _API_FIELD_TO_COLUMN.get(api_field, api_field)


def _column_for(location: tuple[object, ...]) -> str:
    """The column name a Pydantic error belongs to.

    `("warranty", "provider")` is `warranty_provider` in the file, because the
    spreadsheet flattens what the API nests. Anything else is its last part.
    """
    parts = [str(part) for part in location if not isinstance(part, int)]
    if parts[:1] == ["warranty"]:
        return "warranty_" + "_".join(parts[1:]) if len(parts) > 1 else "warranty"
    return parts[-1] if parts else "row"


def _existing_serials(db: Session, workspace_id: uuid.UUID) -> set[str]:
    """Every serial already taken in this workspace.

    Read once rather than per row: a thousand-row file would otherwise be a
    thousand queries, and the answer cannot change mid-import.
    """
    return set(
        db.scalars(
            select(Asset.serial_number).where(Asset.workspace_id == workspace_id)
        )
    )


def run_import(
    db: Session,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    rows: list[dict[str, str]],
    *,
    commit: bool,
) -> ImportReport:
    """Validate every row, and create the good ones when `commit` is set.

    One pass, one set of rules, both modes. `validate` is this function with
    the writes skipped, so a dry run cannot report a row as valid that the
    real run then rejects.

    Duplicate serials are caught twice over, because they arrive two ways: a
    serial already in the database, and a serial repeated inside the file
    itself. The second is invisible to the database until the first of the
    pair is written, which is why `seen` is tracked here.
    """
    report = ImportReport(total_rows=len(rows))
    taken = _existing_serials(db, workspace_id)
    seen: set[str] = set()

    for offset, row in enumerate(rows):
        number = FIRST_DATA_ROW + offset
        serial = row.get("serial_number", "").strip()

        if serial and (serial in taken or serial in seen):
            report.errors.append(RowError(number, "serial_number", "duplicate"))
            report.skipped += 1
            continue

        try:
            data = AssetCreate(**_to_payload(row))
        except ValidationError as error:
            report.errors.extend(
                RowError(number, _column_for(entry["loc"]), entry["msg"])
                for entry in error.errors()
            )
            report.skipped += 1
            continue

        # Run the service-level rules in **both** modes. They live inside
        # create_asset, which only the commit path calls — so checking them
        # here is what stops a dry run calling a row valid that the real run
        # then refuses. Vendor and category presence is the obvious one: the
        # schema cannot see it, because either an id or a name will do.
        try:
            asset_validation.validate_required_catalog_refs(data)
            asset_validation.validate_references(db, workspace_id, data)
        except AssetValidationError as error:
            report.errors.extend(
                RowError(number, _column_for_field(entry["loc"][-1]), entry["msg"])
                for entry in error.detail
            )
            report.skipped += 1
            continue

        if serial:
            seen.add(serial)

        if not commit:
            report.valid += 1
            continue

        # A savepoint per row: a row that fails a database-level rule rolls
        # back only itself, leaving the rows before it intact. That is what
        # makes {"created": 47, "skipped": 3} possible.
        try:
            with db.begin_nested():
                asset_service.create_asset(db, workspace_id, created_by_user_id, data)
        except AssetValidationError as error:
            report.errors.extend(
                RowError(number, _column_for_field(entry["loc"][-1]), entry["msg"])
                for entry in error.detail
            )
            report.skipped += 1
            seen.discard(serial)
        except DuplicateSerialNumber:
            report.errors.append(RowError(number, "serial_number", "duplicate"))
            report.skipped += 1
        except UnknownDocument:  # pragma: no cover - a file cannot cite documents
            report.errors.append(RowError(number, "document_ids", "unknown document"))
            report.skipped += 1
            seen.discard(serial)
        else:
            report.valid += 1
            report.created += 1

    return report
