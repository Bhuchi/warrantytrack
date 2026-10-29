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

CSV and `.xlsx`, because README.md scopes Leg A as "bulk import (CSV/Excel)"
and docs/api.md calls the endpoint "Bulk CSV/Excel import". Both formats are
reduced to the same `list[dict[str, str]]` as early as possible, so every rule
below runs once rather than once per format. `.xls` is not supported and is
named nowhere in the project.
"""

from __future__ import annotations

import csv
import io
import uuid
import zipfile
from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

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


#: The first bytes of every .xlsx file. An .xlsx is a zip archive, so it
#: always starts "PK". Sniffing the content beats trusting Content-Type,
#: which browsers and curl get wrong constantly — and beats trusting the
#: filename, which the raw-body upload does not carry at all.
_XLSX_MAGIC = b"PK\x03\x04"


class ImportError_(Exception):
    """The file itself is unusable — not a row problem, a file problem."""


def parse(raw: bytes) -> list[dict[str, str]]:
    """Rows from either supported format, chosen by looking at the bytes.

    README.md scopes this as "bulk import (CSV/Excel)", so both are accepted
    and neither is the caller's problem to declare.
    """
    if raw.startswith(_XLSX_MAGIC):
        return parse_xlsx(raw)
    return parse_csv(raw)


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

    return _checked(
        [name or "" for name in reader.fieldnames],
        [[row.get(name) for name in reader.fieldnames] for row in reader],
    )


def _cell_text(value: object) -> str:
    """One spreadsheet cell as the string the rest of this module expects.

    Excel stores a date as a real date, so `str()` on it gives
    "2025-03-01 00:00:00" — which Pydantic then rejects as a date. Formatting
    it back to ISO is what makes a `.xlsx` behave like the CSV of the same
    sheet. A number typed into a price cell arrives as a float, and `52000.0`
    would be an odd thing to show back to someone who typed `52000`.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_xlsx(raw: bytes) -> list[dict[str, str]]:
    """The first worksheet of an .xlsx file, as the same rows a CSV gives.

    `read_only` and `data_only` on purpose: the first streams rather than
    building the whole sheet in memory, and the second takes the cached result
    of a formula instead of the formula text, so a price of `=A1*2` imports as
    a number rather than as "=A1*2".

    Only the first sheet. A workbook whose second tab holds notes is far more
    likely than one meant to import twice.
    """
    try:
        workbook = load_workbook(
            io.BytesIO(raw), read_only=True, data_only=True
        )
    except (InvalidFileException, zipfile.BadZipFile) as error:
        raise ImportError_(
            "That is not a readable .xlsx file. Save it as Excel Workbook "
            "(.xlsx) or as CSV and try again."
        ) from error

    try:
        sheet = workbook.worksheets[0]
        rows = [[_cell_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()

    if not rows:
        raise ImportError_("The file is empty.")

    return _checked(rows[0], rows[1:])


def _checked(
    header: list[str], rows: list[list[object]]
) -> list[dict[str, str]]:
    """Shared tail for both formats: verify the header, then shape the rows.

    One place, so a rule like "department may be left out entirely" cannot
    hold for CSV and quietly not for Excel.
    """
    names = [str(name or "").strip() for name in header]

    missing = [name for name in REQUIRED_COLUMNS if name not in set(names)]
    if missing:
        raise ImportError_(f"Missing required column(s): {', '.join(missing)}")

    shaped = [
        {
            name: str(value if value is not None else "").strip()
            for name, value in zip(names, row)
            if name
        }
        for row in rows
    ]

    # A spreadsheet's "last row" is often a few hundred blank ones that Excel
    # kept because the user once clicked there. Dropping them is kinder than
    # reporting four hundred "Field required" errors.
    shaped = [row for row in shaped if any(row.values())]

    if len(shaped) > MAX_ROWS:
        raise ImportError_(
            f"{len(shaped)} rows is more than the {MAX_ROWS}-row limit for one import."
        )

    return shaped


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
