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

from pydantic import BaseModel, ConfigDict

from app.models.asset import Asset, AssetCondition
from app.models.document import DocumentKind, DocumentStatus
from app.services import warranty as warranty_service
from app.services.warranty import WarrantyStatus


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
            location=asset.location,
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
    location: str | None
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
            location=asset.location,
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
