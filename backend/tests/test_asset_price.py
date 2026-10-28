"""Price cannot be negative (CLOUDAPPG5-118).

Not a documented rule — `docs/erd.md` and the model only say how price is
*stored* ("numeric 12,2 — never float"), nothing about its range. This is a
guard against a typo rather than a requirement, and it is recorded as such.

It is reachable from the real form, not only by direct API call: the price box
in `ReceiptReview.tsx` is a plain text input with `inputMode="decimal"` and no
`min`, so the browser happily submits "-500". Task 4 asks for validation to
hold server-side even when the frontend validates first; here the frontend does
not validate at all, so this is the only check there is.

Zero is allowed. A donated or transferred asset is still an asset worth
tracking, and its warranty still matters.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Vendor


def body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
    }
    payload.update(overrides)
    return payload


def fields_in(response) -> set[str]:
    return {entry["loc"][1] for entry in response.json()["detail"]}


@pytest.mark.parametrize("value", ["-500.00", "-0.01", "-1"])
def test_a_negative_price_is_rejected(api: TestClient, value: str) -> None:
    response = api.post("/assets", json=body(price=value))

    assert response.status_code == 422
    assert "price" in fields_in(response)


def test_a_price_of_zero_is_accepted(api: TestClient) -> None:
    """A donated asset costs nothing and is still worth tracking."""
    response = api.post("/assets", json=body(price="0.00"))

    assert response.status_code == 201
    assert response.json()["price"] == "0.00"


def test_an_ordinary_price_is_unaffected(api: TestClient) -> None:
    response = api.post("/assets", json=body(price="32900.00"))

    assert response.status_code == 201
    assert response.json()["price"] == "32900.00"


def test_a_negative_price_is_rejected_on_patch(api: TestClient) -> None:
    created = api.post("/assets", json=body()).json()

    response = api.patch(f"/assets/{created['id']}", json={"price": "-1.00"})

    assert response.status_code == 422
    assert api.get(f"/assets/{created['id']}").json()["price"] == "32900.00"


def test_patch_can_still_clear_the_price(api: TestClient) -> None:
    """The guard must not block the way to unset an optional column."""
    created = api.post("/assets", json=body()).json()

    updated = api.patch(f"/assets/{created['id']}", json={"price": None})

    assert updated.status_code == 200
    assert updated.json()["price"] is None


def test_a_rejected_price_writes_nothing(api: TestClient, db: Session) -> None:
    """Schema validation runs first, so the vendor is never created either."""
    response = api.post(
        "/assets", json=body(price="-500.00", vendor_name="Brand New Vendor")
    )

    assert response.status_code == 422
    assert db.scalars(select(Asset)).all() == []
    assert db.scalars(select(Vendor)).all() == []
