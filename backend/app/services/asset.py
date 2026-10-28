"""Query logic for the Assets endpoints.

Routes stay thin: they say who is asking and what they are filtering by, and
hand off here. All SQL lives in services, so it is testable without HTTP and
reusable — the dashboard and the bulk importer will call into this module too.

Every query starts by narrowing to one workspace. That is not a convenience:
it is the whole tenancy boundary (docs/architecture.md). An asset in another
workspace is simply not in the result set, which is what makes
`GET /assets/{id}` return 404 rather than 403 without the route having to think
about it.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models.asset import Asset
from app.models.catalog import Category, Vendor
from app.models.document import AssetDocument, Document
from app.models.warranty import Warranty
from app.schemas.asset import AssetCreate, AssetUpdate, WarrantyInput
from app.services import catalog as catalog_service
from app.services import warranty as warranty_service
from app.services.warranty import WarrantyStatus
from app.utils.dates import add_months


class DuplicateSerialNumber(Exception):
    """This workspace already has an asset with that serial number."""


class UnknownDocument(Exception):
    """A document_id does not exist in this workspace."""


def _status_condition(status: WarrantyStatus, today: date) -> ColumnElement[bool]:
    """Express one warranty status as SQL, matching compute_status() exactly.

    The two have to agree: this decides which rows come back, and
    `compute_status` decides what each row is then labelled. If they drifted,
    a filter for "expired" could return a row the response then calls
    "expiring_soon".

    The boundaries are therefore the same ones that function documents:
    `end_date == today` is not yet past, so it is expiring_soon; exactly
    EXPIRING_SOON_DAYS away is still expiring_soon.

    `unknown` is the absence of a warranty row, which is why the caller must
    outer-join rather than inner-join — an inner join would drop exactly the
    rows this status is about.
    """
    soon = today + timedelta(days=warranty_service.EXPIRING_SOON_DAYS)

    if status is WarrantyStatus.unknown:
        return Warranty.id.is_(None)
    if status is WarrantyStatus.expired:
        return Warranty.end_date < today
    if status is WarrantyStatus.expiring_soon:
        return and_(Warranty.end_date >= today, Warranty.end_date <= soon)
    return Warranty.end_date > soon


def _conditions(
    workspace_id: uuid.UUID,
    q: str | None,
    status: WarrantyStatus | None,
    category_id: uuid.UUID | None,
    vendor_id: uuid.UUID | None,
    today: date,
) -> list[ColumnElement[bool]]:
    """The WHERE clause, built once and used by both the count and the page.

    Sharing it is what keeps `total` honest: if the two queries could drift,
    the screen would say "1-20 of 128" while filtering down to 40.
    """
    conditions: list[ColumnElement[bool]] = [Asset.workspace_id == workspace_id]

    if category_id is not None:
        conditions.append(Asset.category_id == category_id)
    if vendor_id is not None:
        conditions.append(Asset.vendor_id == vendor_id)
    if q:
        # Name, serial and invoice number — what a user has in front of them
        # when hunting for one asset. ilike so case does not matter.
        like = f"%{q}%"
        conditions.append(
            or_(
                Asset.name.ilike(like),
                Asset.serial_number.ilike(like),
                Asset.invoice_number.ilike(like),
            )
        )
    if status is not None:
        conditions.append(_status_condition(status, today))

    return conditions


def list_assets(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    q: str | None = None,
    status: WarrantyStatus | None = None,
    category_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    today: date | None = None,
) -> tuple[int, list[Asset]]:
    """Return (total matching, one page of assets) for the Assets List.

    `today` is injectable so tests can pin the clock when checking the status
    filter's boundaries; callers pass nothing in production.

    Two queries rather than one: a COUNT over every match, then the page. The
    screen needs both numbers and a window function would compute the total
    once per row.

    Ordering is newest-first with `id` as a tiebreaker. The tiebreaker is not
    cosmetic — without a deterministic sort, two assets created in the same
    transaction could swap places between page 1 and page 2, so one would
    appear twice and another not at all.
    """
    today = today or date.today()
    conditions = _conditions(workspace_id, q, status, category_id, vendor_id, today)

    total = db.scalar(
        select(func.count())
        .select_from(Asset)
        .outerjoin(Warranty, Warranty.asset_id == Asset.id)
        .where(*conditions)
    )

    items = (
        db.scalars(
            select(Asset)
            # Outer, not inner: assets without a warranty are `unknown`, not
            # missing. The same join backs both the filter and the eager load.
            .outerjoin(Warranty, Warranty.asset_id == Asset.id)
            .options(
                contains_eager(Asset.warranty),
                # Loaded here so building each row does not fire two more
                # queries per asset for the names the table draws.
                joinedload(Asset.category),
                joinedload(Asset.vendor),
            )
            .where(*conditions)
            .order_by(Asset.created_at.desc(), Asset.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )

    return total or 0, list(items)


def _resolve_catalog_id(
    db: Session,
    model: type[Category] | type[Vendor],
    workspace_id: uuid.UUID,
    given_id: uuid.UUID | None,
    given_name: str | None,
) -> uuid.UUID | None:
    """Turn "an id, or a name, or neither" into an id.

    An explicit id wins: once the form has a real dropdown it will send one,
    and it should not be second-guessed by a stale name sitting beside it.
    """
    if given_id is not None:
        return given_id
    if given_name and given_name.strip():
        return catalog_service.get_or_create(db, model, workspace_id, given_name).id
    return None


def create_asset(
    db: Session,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    data: AssetCreate,
) -> Asset:
    """Create one asset, with its warranty and document links.

    **The only way an asset is written.** Manual entry, confirmed OCR and bulk
    import all come through here — docs/api.md makes that a rule rather than a
    convention, so the required fields, the vendor lookup and the end-date
    calculation cannot drift between the three paths.

    Raises DuplicateSerialNumber or UnknownDocument; the route turns those into
    409 and 422. They are exceptions rather than return codes because every
    caller has to handle them and none of them can continue without doing so.
    """
    clash = db.scalars(
        select(Asset).where(
            Asset.workspace_id == workspace_id,
            Asset.serial_number == data.serial_number,
        )
    ).first()
    if clash is not None:
        raise DuplicateSerialNumber(data.serial_number)

    asset = Asset(
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        name=data.name.strip(),
        serial_number=data.serial_number.strip(),
        condition=data.condition,
        purchase_date=data.purchase_date,
        price=data.price,
        currency=data.currency,
        invoice_number=data.invoice_number,
        category_id=_resolve_catalog_id(
            db, Category, workspace_id, data.category_id, data.category_name
        ),
        vendor_id=_resolve_catalog_id(
            db, Vendor, workspace_id, data.vendor_id, data.vendor_name
        ),
        department_id=data.department_id,
        location=data.location,
        image_key=data.image_key,
        location_image_key=data.location_image_key,
        assigned_to_user_id=data.assigned_to_user_id,
    )
    db.add(asset)
    db.flush()

    if data.warranty is not None:
        db.add(
            Warranty(
                workspace_id=workspace_id,
                asset_id=asset.id,
                provider=data.warranty.provider,
                start_date=data.warranty.start_date,
                # Stored, not derived on read: the dashboard, the expiring list
                # and the nightly e-mail job all filter on this column.
                end_date=add_months(
                    data.warranty.start_date, data.warranty.duration_months
                ),
            )
        )

    if data.document_ids:
        _link_documents(db, workspace_id, asset.id, data.document_ids)

    db.flush()
    db.refresh(asset)
    return asset


def _link_documents(
    db: Session,
    workspace_id: uuid.UUID,
    asset_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> None:
    """Attach already-uploaded documents to a new asset.

    Every id is checked to be in *this* workspace first. Without that, a
    caller could cite someone else's receipt and the asset detail screen would
    hand out a presigned URL to it — the join row's own workspace_id would not
    save us, because we would be the ones writing it.
    """
    found = set(
        db.scalars(
            select(Document.id).where(
                Document.workspace_id == workspace_id,
                Document.id.in_(document_ids),
            )
        )
    )
    missing = set(document_ids) - found
    if missing:
        raise UnknownDocument(sorted(str(value) for value in missing))

    for document_id in dict.fromkeys(document_ids):
        db.add(
            AssetDocument(
                asset_id=asset_id,
                document_id=document_id,
                workspace_id=workspace_id,
            )
        )


#: Fields copied straight from the payload onto the asset when present.
_PLAIN_UPDATE_FIELDS = (
    "name",
    "serial_number",
    "condition",
    "purchase_date",
    "price",
    "currency",
    "invoice_number",
    "department_id",
    "location",
    "image_key",
    "location_image_key",
)


def update_asset(
    db: Session, asset: Asset, data: AssetUpdate
) -> Asset:
    """Apply a partial update to an asset already fetched for this workspace.

    Takes the Asset rather than an id because the caller has already loaded it
    — which is also what proves it is in the caller's workspace, so this
    function cannot be tricked into editing someone else's row.

    `model_fields_set` is what makes PATCH partial: it holds only the keys the
    client actually sent, so omitting `invoice_number` leaves it untouched
    while sending it as `null` clears it. Reading `data.invoice_number is not
    None` instead would make it impossible to ever clear a field.
    """
    sent = data.model_fields_set

    if "serial_number" in sent and data.serial_number != asset.serial_number:
        clash = db.scalars(
            select(Asset).where(
                Asset.workspace_id == asset.workspace_id,
                Asset.serial_number == data.serial_number,
                Asset.id != asset.id,
            )
        ).first()
        if clash is not None:
            raise DuplicateSerialNumber(data.serial_number)

    for field in _PLAIN_UPDATE_FIELDS:
        if field in sent:
            value = getattr(data, field)
            setattr(asset, field, value.strip() if isinstance(value, str) else value)

    # A name and an id are two ways of setting the same column, so they share
    # one branch: whichever the client sent decides the new value.
    if "category_id" in sent or "category_name" in sent:
        asset.category_id = _resolve_catalog_id(
            db, Category, asset.workspace_id, data.category_id, data.category_name
        )
    if "vendor_id" in sent or "vendor_name" in sent:
        asset.vendor_id = _resolve_catalog_id(
            db, Vendor, asset.workspace_id, data.vendor_id, data.vendor_name
        )

    if "warranty" in sent:
        _apply_warranty(db, asset, data.warranty)

    db.flush()
    db.refresh(asset)
    return asset


def _apply_warranty(db: Session, asset: Asset, warranty: WarrantyInput | None) -> None:
    """Add, replace or remove an asset's warranty.

    `"warranty": null` removes it — an asset can legitimately have none, and
    the status simply becomes `unknown`. Sending an object either updates the
    existing row or creates one, recomputing `end_date` from the new start and
    duration so a stored date never survives the inputs it came from.
    """
    if warranty is None:
        if asset.warranty is not None:
            db.delete(asset.warranty)
        return

    end_date = add_months(warranty.start_date, warranty.duration_months)

    if asset.warranty is None:
        db.add(
            Warranty(
                workspace_id=asset.workspace_id,
                asset_id=asset.id,
                provider=warranty.provider,
                start_date=warranty.start_date,
                end_date=end_date,
            )
        )
    else:
        asset.warranty.provider = warranty.provider
        asset.warranty.start_date = warranty.start_date
        asset.warranty.end_date = end_date


def delete_asset(db: Session, asset: Asset) -> None:
    """Remove an asset, its warranty and its document links.

    What goes and what stays is decided by the schema, not by code here
    (docs/erd.md): the warranty row and the `asset_documents` join rows are
    `ON DELETE CASCADE`, so they go with it, while the `documents` themselves
    are untouched — one invoice can back several assets, and the S3 object
    outlives any single one of them.

    Notifications about the asset also survive, with `asset_id` set to NULL:
    "your warranty expired" stays true after the asset is gone, it just stops
    being a link.
    """
    db.delete(asset)
    db.flush()


def get_asset(
    db: Session, workspace_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset | None:
    """One asset with everything the detail screen draws, or None.

    None covers both "no such asset" and "exists, but in a workspace you are
    not in" — the caller turns both into 404. Telling them apart would confirm
    the record exists to someone who should not know, which is the leak
    docs/api.md warns against.
    """
    return (
        db.scalars(
            select(Asset)
            .options(
                joinedload(Asset.warranty),
                joinedload(Asset.category),
                joinedload(Asset.vendor),
                joinedload(Asset.department),
                joinedload(Asset.assigned_to),
                joinedload(Asset.documents),
            )
            .where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
        )
        .unique()
        .one_or_none()
    )
