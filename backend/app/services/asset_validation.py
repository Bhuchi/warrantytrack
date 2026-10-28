"""Server-side validation for saving an asset (CLOUDAPPG5-118).

A module rather than endpoint code, because four callers need the same rules
and must not drift: manual entry (`POST /assets`), editing (`PATCH`), Leg B's
OCR confirm, and the bulk importer. `docs/api.md` already makes
`asset_service.create_asset()` the single write path; this is the single
*gate* in front of it.

Two layers, split on purpose:

- **Pydantic** (`app/schemas/asset.py`) checks shape — present, non-blank,
  in range, parseable. It runs before any database work and already reports
  one entry per bad field.
- **This module** checks everything that needs the database: that an id the
  caller sent actually exists *and belongs to their workspace*.

The second layer is not a nicety. Nothing stops a caller sending another
workspace's `vendor_id`, and the foreign key does not either — it points at
`vendors.id` with no tenant predicate. Without this check an asset can be
attached to another organization's vendor, and `GET /assets/{id}` then hands
that organization's vendor name back. Tenancy is enforced in queries
(docs/architecture.md), so a write that takes an id on trust escapes it.

Errors are raised together, in FastAPI's own 422 shape, so a caller fixing a
form sees every problem at once rather than one per round trip.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Category, Department, Location, Vendor
from app.models.membership import Membership


@dataclass(frozen=True)
class FieldError:
    """One problem, named against the field that caused it."""

    field: str
    message: str
    type: str = "value_error"

    def as_detail(self) -> dict[str, Any]:
        """The entry as FastAPI writes it for a Pydantic failure.

        Matching that shape exactly means a caller cannot tell whether a
        message came from the schema or from here — `loc[1]` is the field
        name either way, which is what a form needs to show the error inline.
        """
        return {"type": self.type, "loc": ["body", self.field], "msg": self.message}


class AssetValidationError(Exception):
    """Carries every field problem found, not just the first."""

    def __init__(self, errors: list[FieldError]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} field(s) failed validation")

    @property
    def detail(self) -> list[dict[str, Any]]:
        """Ready to hand straight to HTTPException(status_code=422)."""
        return [error.as_detail() for error in self.errors]


#: What a committed asset must always have —
#: docs/database/WarrantyTrack-ERD-v1.2/README.md, "Explicit design decisions".
#: `AssetCreate` enforces these through the schema; this list is for the edit
#: path, which must not be able to take one away afterwards.
#:
#: Until now `PATCH {"name": null}` set the column to NULL, the flush raised an
#: IntegrityError and the caller got a 500 — neither clear nor per-field.
_REQUIRED_SCALARS = (
    "name",
    "serial_number",
    "condition",
    "purchase_date",
    "price",
    "invoice_number",
)

#: The same rule for the two references that are required rather than optional.
#: Clearing one means sending its id as null without supplying a name.
_REQUIRED_REFERENCES = (("vendor", "vendor_id", "vendor_name"),
                        ("category", "category_id", "category_name"))


def validate_required_catalog_refs(data: Any) -> None:
    """Vendor and category must be given, by id or by name.

    Here rather than in a Pydantic `model_validator` because a model-level
    validator reports `loc: ["body"]` — the form cannot show that against a
    field, and the response echoes the whole payload back. A `FieldError`
    names `category_id`, which is what "clear per-field error messages" in
    CLOUDAPPG5-118 asks for.

    Create only. On update the pair is already there, and
    `validate_nothing_required_is_cleared` stops it being removed.
    """
    errors: list[FieldError] = []

    for label, id_field, name_field in _REQUIRED_REFERENCES:
        given_name = getattr(data, name_field, None) or ""
        if getattr(data, id_field, None) is None and not given_name.strip():
            errors.append(
                FieldError(
                    id_field,
                    f"{id_field} or {name_field} is required",
                    type="missing",
                )
            )

    if errors:
        raise AssetValidationError(errors)


def validate_nothing_required_is_cleared(data: Any) -> None:
    """Refuse an edit that would strip a required field from a saved asset.

    Only looks at what the caller actually sent: `model_fields_set` separates
    "left alone" from "explicitly set to null", and only the second is a
    problem. Omitting a field on PATCH is the normal case and stays untouched.

    Create does not need this — the schema already demands every one of these.
    """
    sent = data.model_fields_set
    errors: list[FieldError] = []

    for field in _REQUIRED_SCALARS:
        if field in sent and getattr(data, field, None) is None:
            errors.append(
                FieldError(field, "Field required", type="missing")
            )

    for label, id_field, name_field in _REQUIRED_REFERENCES:
        touched = id_field in sent or name_field in sent
        if not touched:
            continue
        given_name = getattr(data, name_field, None) or ""
        if getattr(data, id_field, None) is None and not given_name.strip():
            errors.append(
                FieldError(id_field, f"An asset must have a {label}", type="missing")
            )

    if "warranty" in sent and getattr(data, "warranty", None) is None:
        errors.append(
            FieldError("warranty", "An asset must have a warranty", type="missing")
        )

    if errors:
        raise AssetValidationError(errors)


#: The asset fields that point at a workspace-scoped catalog row.
_CATALOG_REFERENCES = (
    ("category_id", Category, "category"),
    ("vendor_id", Vendor, "vendor"),
    ("department_id", Department, "department"),
    ("location_id", Location, "location"),
)


def validate_references(
    db: Session, workspace_id: uuid.UUID, data: Any
) -> None:
    """Check every id the caller sent belongs to their workspace.

    Works for both `AssetCreate` and `AssetUpdate`: a `None` means "not sent"
    on create and "clear this" on update, and neither needs checking — only a
    concrete id does. `getattr` with a default covers the fields `AssetUpdate`
    deliberately does not accept, such as `assigned_to_user_id`.

    Collects rather than raising on the first problem, so a form with two bad
    pickers reports both.
    """
    errors: list[FieldError] = []

    for field, model, label in _CATALOG_REFERENCES:
        given: uuid.UUID | None = getattr(data, field, None)
        if given is None:
            continue
        found = db.scalar(
            select(model.id).where(
                model.id == given, model.workspace_id == workspace_id
            )
        )
        if found is None:
            # Deliberately the same message whether the row is missing or
            # belongs to someone else: saying which would confirm that another
            # workspace holds that id.
            errors.append(FieldError(field, f"No such {label} in this workspace"))

    assignee: uuid.UUID | None = getattr(data, "assigned_to_user_id", None)
    if assignee is not None:
        member = db.scalar(
            select(Membership.id).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == assignee,
            )
        )
        if member is None:
            errors.append(
                FieldError(
                    "assigned_to_user_id",
                    "That user is not a member of this workspace",
                )
            )

    if errors:
        raise AssetValidationError(errors)
