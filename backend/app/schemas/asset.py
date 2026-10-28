"""Response shapes for the Assets endpoints.

These mirror docs/api.md -> Assets exactly. The Assets List (D05) and Asset
Detail (D08) screens are written against these shapes, so the field names and
nesting here ARE the contract.

Two shapes on purpose: the list is deliberately lightweight (D05 renders a
table of many rows and needs none of the purchase detail), while the detail
carries the nested category/vendor/department objects, the warranty and the
documents. Sending the detail shape for every row would make the list payload
several times larger for columns nobody draws.

The `from_asset` builders live here rather than in the service because they are
presentation: flattening `asset.category.name` into `category_name` is about
what the screen draws, not about business logic. The one computed value,
warranty status, is delegated to app/services/warranty.py — the rule has a
single home and this is not it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models.asset import Asset, AssetCondition
from app.models.document import DocumentKind, DocumentStatus
from app.services import warranty as warranty_service
from app.services.warranty import WarrantyStatus


#: Text that must actually say something. Stripped first, then required to be
#: non-empty — checking length before stripping would let "   " through and
#: store an asset with a blank name.
AssetName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
SerialNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
#: Optional, but "   " is a mistake rather than a value. CLOUDAPPG5-118 asks
#: for whitespace-only invoice numbers to be rejected, so this errors rather
#: than quietly becoming null — the user typed something and should be told it
#: did not count. Omitting the field, or sending null, remains fine.
InvoiceNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


def _blank_to_none(value: object) -> object:
    """Treat a whitespace-only string as "not given"."""
    if isinstance(value, str):
        return value.strip() or None
    return value


#: Free text where blank genuinely means absent. Unlike the invoice number,
#: there is nothing to tell the user off about: leaving the step 3 note empty,
#: or typing spaces into it, both mean the same thing.
#: The length limit sits on the `str` arm, not on the union: applied to the
#: whole thing it would be handed a None and raise.
StorageNote = Annotated[
    Annotated[str, StringConstraints(max_length=200)] | None,
    BeforeValidator(_blank_to_none),
]


class WarrantyInput(BaseModel):
    """The warranty part of POST /assets.

    The client sends a start date and a duration; the backend works out
    `end_date`. That split is the frontend's expectation, not an invention —
    `warrantyEndLabel` in add-asset/draft.ts computes the same value for the
    form's preview and says outright that it is "display only: the backend
    computes the real end date".
    """

    provider: str | None = None
    start_date: date
    duration_months: int = Field(gt=0, le=600)


class AssetCreate(BaseModel):
    """POST /assets.

    Required fields follow the team's 18 Oct decision, recorded in
    docs/frontend-plan.md and enforced by `isReceiptComplete` in
    add-asset/draft.ts: name, vendor, purchase date, price, condition — plus
    the serial number, which the same decision made non-skippable.

    Category, vendor, department and location are all optional, as are the
    invoice number, the storage note, the documents and the warranty itself.

    **Category, vendor and location accept either an id or a name.** The form
    and OCR produce "Power Buy", not a UUID, and there is no picker in the UI
    yet; a name is looked up in this workspace's catalog and created if
    missing. Sending the id is still supported and is what a dropdown will do
    once one exists.
    """

    name: AssetName
    serial_number: SerialNumber
    condition: AssetCondition
    purchase_date: date
    price: Decimal
    currency: str = Field(default="THB", min_length=3, max_length=3)
    invoice_number: InvoiceNumber | None = None

    category_id: uuid.UUID | None = None
    category_name: str | None = Field(default=None, max_length=120)
    vendor_id: uuid.UUID | None = None
    vendor_name: str | None = Field(default=None, max_length=120)
    department_id: uuid.UUID | None = None
    # The site the asset lives at ("HQ Floor 3"), from the `locations` list.
    # Not to be confused with `storage_note` below.
    location_id: uuid.UUID | None = None
    location_name: str | None = Field(default=None, max_length=120)

    # Free text about where the box is kept ("Box is on the top shelf"). The
    # Add Asset form labels this field "Note" (BoxPhotoStep.tsx) and FE-11
    # calls it a free-text note, so that is what the API calls it. It is stored
    # in the `assets.location` column, which predates the name.
    storage_note: StorageNote = None
    image_key: str | None = Field(default=None, max_length=1024)
    location_image_key: str | None = Field(default=None, max_length=1024)

    document_ids: list[uuid.UUID] = Field(default_factory=list)
    assigned_to_user_id: uuid.UUID | None = None
    warranty: WarrantyInput | None = None

    @model_validator(mode="after")
    def check_vendor_given(self) -> AssetCreate:
        """Vendor is required, by either route.

        Rejected here rather than in the service so the caller gets a 422 with
        the field named, which is what the form shows inline.
        """
        if self.vendor_id is None and not (self.vendor_name or "").strip():
            raise ValueError("vendor_id or vendor_name is required")
        return self


class AssetUpdate(BaseModel):
    """PATCH /assets/{id} — any subset of the create fields.

    Every field is optional, and "absent" means something different from
    "null": omitting `invoice_number` leaves it alone, sending it as `null`
    clears it. The service reads `model_fields_set` to tell the two apart,
    which is why nothing here has a non-None default.

    Two fields from POST are deliberately **not** accepted:

    - `assigned_to_user_id` — assignment has its own endpoint
      (`POST /assets/{id}/assign`) which is admin-only. Allowing it here would
      be a second door into the same change with weaker rules.
    - `document_ids` — "replace the list" and "add to the list" are both
      reasonable readings and the contract does not say which. Documents are
      attached at creation; changing them needs its own agreed shape.
    """

    name: AssetName | None = None
    serial_number: SerialNumber | None = None
    condition: AssetCondition | None = None
    purchase_date: date | None = None
    price: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    invoice_number: InvoiceNumber | None = None

    category_id: uuid.UUID | None = None
    category_name: str | None = Field(default=None, max_length=120)
    vendor_id: uuid.UUID | None = None
    vendor_name: str | None = Field(default=None, max_length=120)
    department_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    location_name: str | None = Field(default=None, max_length=120)

    storage_note: StorageNote = None
    image_key: str | None = Field(default=None, max_length=1024)
    location_image_key: str | None = Field(default=None, max_length=1024)

    warranty: WarrantyInput | None = None


class CatalogRef(BaseModel):
    """A catalog row as it appears nested inside an asset."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class AssignedToRef(BaseModel):
    """Who the asset is assigned to, for the detail screen's header."""

    user_id: uuid.UUID
    display_name: str | None


class WarrantyDetail(BaseModel):
    """The cover on an asset, with its status computed at read time.

    `status` is not a column and must never become one — see the Warranty
    model. It is derived here from `end_date` every time the asset is read.
    """

    provider: str | None
    start_date: date | None
    end_date: date
    status: WarrantyStatus


class DocumentRef(BaseModel):
    """A receipt or invoice backing this asset.

    `s3_key`, never a URL: the bucket is private and the API hands out
    short-lived presigned GETs, so a stored URL would already be expired.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    s3_key: str
    status: DocumentStatus
    kind: DocumentKind


class AssetListItem(BaseModel):
    """One row of the Assets List (D05).

    `category_name`, `vendor_name` and `location` are flattened rather than
    nested: the table draws them as plain cells, and the frontend asked for
    exactly these three in frontend/src/types/assetList.ts.

    `location` here is the **site** ("HQ Floor 3"), not the storage note. The
    D05 table's LOCATION column sits between CATEGORY and VENDOR, both of
    which are catalog lists, and the planned filter for it is a dropdown
    (AssetsList.tsx) — which only a list can fill. The storage note is free
    text and belongs on the detail screen, not in a 14%-wide column.
    """

    id: uuid.UUID
    name: str
    serial_number: str
    purchase_date: date
    warranty_end_date: date | None
    warranty_status: WarrantyStatus
    assigned_to_user_id: uuid.UUID | None
    category_name: str | None
    vendor_name: str | None
    location: str | None

    @classmethod
    def from_asset(cls, asset: Asset, today: date | None = None) -> AssetListItem:
        """Build a row from a loaded Asset.

        Every attribute touched here is eager-loaded by the service, so this
        does not fire a query per row.
        """
        return cls(
            id=asset.id,
            name=asset.name,
            serial_number=asset.serial_number,
            purchase_date=asset.purchase_date,
            warranty_end_date=asset.warranty.end_date if asset.warranty else None,
            warranty_status=warranty_service.status_for_asset(asset, today),
            assigned_to_user_id=asset.assigned_to_user_id,
            category_name=asset.category.name if asset.category else None,
            vendor_name=asset.vendor.name if asset.vendor else None,
            location=asset.location_ref.name if asset.location_ref else None,
        )


class AssetList(BaseModel):
    """One page of the Assets List: the rows plus what paging needs.

    `total` counts every asset matching the filters, not just this page — the
    screen shows "1-20 of 128" and has to know the 128.
    """

    items: list[AssetListItem]
    total: int
    page: int
    page_size: int


class AssetDetail(BaseModel):
    """The whole asset, for Asset Detail (D08)."""

    id: uuid.UUID
    name: str
    serial_number: str
    condition: AssetCondition
    purchase_date: date
    price: Decimal | None
    currency: str
    invoice_number: str | None
    category: CatalogRef | None
    vendor: CatalogRef | None
    department: CatalogRef | None
    # The site, nested like category and vendor — what docs/erd.md proposed.
    location: CatalogRef | None
    # Free text from Add Asset step 3, shown under "Box / Storage" on D08.
    storage_note: str | None
    assigned_to: AssignedToRef | None
    warranty: WarrantyDetail | None
    documents: list[DocumentRef]
    created_at: datetime

    @classmethod
    def from_asset(cls, asset: Asset, today: date | None = None) -> AssetDetail:
        """Build the detail payload from a loaded Asset."""
        warranty = asset.warranty

        return cls(
            id=asset.id,
            name=asset.name,
            serial_number=asset.serial_number,
            condition=asset.condition,
            purchase_date=asset.purchase_date,
            price=asset.price,
            currency=asset.currency,
            invoice_number=asset.invoice_number,
            category=CatalogRef.model_validate(asset.category) if asset.category else None,
            vendor=CatalogRef.model_validate(asset.vendor) if asset.vendor else None,
            department=(
                CatalogRef.model_validate(asset.department) if asset.department else None
            ),
            location=(
                CatalogRef.model_validate(asset.location_ref)
                if asset.location_ref
                else None
            ),
            storage_note=asset.location,
            assigned_to=(
                AssignedToRef(
                    user_id=asset.assigned_to.id,
                    display_name=asset.assigned_to.display_name,
                )
                if asset.assigned_to
                else None
            ),
            warranty=(
                WarrantyDetail(
                    provider=warranty.provider,
                    start_date=warranty.start_date,
                    end_date=warranty.end_date,
                    status=warranty_service.compute_status(warranty.end_date, today),
                )
                if warranty
                else None
            ),
            documents=[DocumentRef.model_validate(doc) for doc in asset.documents],
            created_at=asset.created_at,
        )
