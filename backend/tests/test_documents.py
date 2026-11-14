"""Receipt upload, OCR and confirm (CLOUDAPPG5-95, CLOUDAPPG5-96).

The flow under test:

    POST /documents/presign  ->  PUT the file  ->  POST .../submit
    ->  GET /documents/{id}  ->  POST .../confirm

Runs on the development backends (`local` storage, `fake` OCR), which is what
CI has and what a teammate without AWS has. The Textract parser itself is
tested separately in test_ocr_parse.py.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.services import ocr, storage
from app.models.asset import Asset
from app.models.document import AssetDocument, Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture(autouse=True)
def uploads_in_tmp(tmp_path: Path):
    """Keep each test's uploads in its own directory.

    Autouse because every test here either uploads or checks that nothing was
    uploaded, and a shared directory would leak state between them.
    """
    original = settings.local_upload_dir
    settings.local_upload_dir = str(tmp_path / "uploads")
    try:
        yield
    finally:
        settings.local_upload_dir = original


def asset_entry(**overrides: object) -> dict[str, object]:
    """One reviewed line from the OCR screen, ready for confirm.

    Carries category, invoice number and warranty because confirm goes through
    `asset_service.create_asset()`, which requires them (CLOUDAPPG5-118, from
    docs/database/WarrantyTrack-ERD-v1.2/README.md lines 35-36 — line 27 of the
    same document lists exactly these as what the confirm step validates).

    None of the three come out of Textract: `extracted` holds vendor, purchase
    date, total and line items only. They are the user's edits on the OCR
    Review screen (D07), which has to collect them before confirm can succeed.
    """
    entry: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
        "category_name": "Laptop",
        "invoice_number": "INV-2025-001",
        "warranty": {
            "provider": "Dell",
            "start_date": "2025-03-01",
            "duration_months": 36,
        },
    }
    entry.update(overrides)
    return entry


def presign(api: TestClient, filename: str = "receipt.jpg") -> dict:
    response = api.post(
        "/documents/presign",
        json={"filename": filename, "content_type": "image/jpeg"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def upload(api: TestClient, document_id: str, body: bytes = b"fake-jpeg-bytes") -> None:
    response = api.put(f"/documents/{document_id}/dev-upload", content=body)
    assert response.status_code == 204, response.text


def extracted_document(api: TestClient) -> str:
    """Walk the flow up to `extracted` and return the document id."""
    reserved = presign(api)
    upload(api, reserved["document_id"])
    response = api.post(f"/documents/{reserved['document_id']}/submit")
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "extracted"
    return reserved["document_id"]


# --- presign ---------------------------------------------------------------


def test_presign_reserves_a_row_and_an_upload_url(api: TestClient, db: Session, workspace: Workspace) -> None:
    reserved = presign(api)

    document = db.get(Document, uuid.UUID(reserved["document_id"]))
    assert document is not None
    # Created before the file exists — that is the whole point of presign.
    assert document.status is DocumentStatus.pending
    assert document.workspace_id == workspace.id
    # The key names its tenant and uploader for S3 console browsing.
    assert reserved["s3_key"].startswith("workspaces/")
    assert f"-{workspace.id}/users/" in reserved["s3_key"]
    assert reserved["upload_url"].endswith(f"/documents/{document.id}/dev-upload")


def test_presign_sanitises_the_filename(api: TestClient) -> None:
    """A filename becomes part of an object key, so it cannot carry a path."""
    reserved = presign(api, filename="../../etc/passwd")
    key = reserved["s3_key"]
    assert ".." not in key
    assert "../" not in key
    assert "/users/" in key


# --- submit ----------------------------------------------------------------


def test_submit_without_an_upload_is_a_conflict(api: TestClient) -> None:
    reserved = presign(api)
    response = api.post(f"/documents/{reserved['document_id']}/submit")
    assert response.status_code == 409


def test_submit_extracts_and_records_the_fields(api: TestClient, db: Session) -> None:
    document_id = extracted_document(api)

    document = db.get(Document, uuid.UUID(document_id))
    assert document.status is DocumentStatus.extracted
    assert document.attempts == 1
    assert document.extracted_json["vendor_name"] == "Power Buy"
    # The fake backend deliberately leaves the date blank, like a real photo.
    assert document.extracted_json["purchase_date"] is None
    assert len(document.extracted_json["line_items"]) == 2


def test_a_file_that_is_not_a_receipt_fails_with_advice(
    api: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLOUDAPPG5-148: a product photo or a screenshot is not an invoice."""
    def refuse(*_args: object, **_kwargs: object) -> dict:
        raise ocr.NotAReceipt()

    monkeypatch.setattr(ocr, "extract", refuse)
    document = presign(api, filename="cat.jpg")
    upload(api, document["document_id"])

    submitted = api.post(f"/documents/{document['document_id']}/submit")

    assert submitted.status_code == 202
    for body in (submitted.json(), api.get(f"/documents/{document['document_id']}").json()):
        assert body["status"] == "failed"
        assert body["extracted"] is None
        assert body["error"] == (
            "This doesn't look like an invoice or receipt. Please upload only an invoice or receipt."
        )


def test_a_real_jpeg_survives_the_upload_path(api: TestClient, db: Session) -> None:
    """The stored bytes must be the bytes that were sent.

    Runs on the `local` backend, so it checks our own plumbing rather than
    Textract: a real 73KB JPEG, byte-for-byte, because an upload path that
    mangles binary would show up as unexplainable OCR failures later.
    tests/test_ocr_live.py sends this same file to the real API.
    """
    receipt = Path(__file__).parent / "fixtures" / "receipts" / "jib-receipt.jpg"
    if not receipt.exists():
        pytest.skip(f"fixture not present: {receipt.name}")
    original = receipt.read_bytes()

    reserved = presign(api, filename="jib-receipt.jpg")
    upload(api, reserved["document_id"], body=original)

    stored = storage.read_bytes(reserved["s3_key"])
    assert stored == original
    # A JPEG still starts with the JPEG magic number after the round trip.
    assert stored[:3] == b"\xff\xd8\xff"

    response = api.post(f"/documents/{reserved['document_id']}/submit")
    assert response.status_code == 202
    assert response.json()["status"] == "extracted"


def test_get_returns_what_the_review_screen_polls(api: TestClient) -> None:
    document_id = extracted_document(api)
    response = api.get(f"/documents/{document_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "extracted"
    assert body["error"] is None
    assert body["extracted"]["line_items"][0]["serial_number"] == "ABC123"


# --- tenancy and roles -----------------------------------------------------


def test_another_workspaces_document_is_404(api: TestClient, db: Session, other_workspace: Workspace) -> None:
    """404, not 403 — a 403 would confirm the document exists."""
    theirs = Document(
        workspace_id=other_workspace.id,
        s3_key=f"ws/{other_workspace.id}/{uuid.uuid4()}-theirs.jpg",
        filename="theirs.jpg",
    )
    db.add(theirs)
    db.flush()

    assert api.get(f"/documents/{theirs.id}").status_code == 404
    assert api.post(f"/documents/{theirs.id}/submit").status_code == 404
    assert (
        api.post(f"/documents/{theirs.id}/confirm", json={"assets": [asset_entry()]}).status_code
        == 404
    )


def test_an_employee_sees_only_their_own_uploads(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership
) -> None:
    """CLOUDAPPG5-96: a receipt shows what the company paid for things that are
    none of an employee's business, even when the asset is assigned to them."""
    colleague = User(cognito_sub=f"other-{uuid.uuid4()}", email=f"o-{uuid.uuid4()}@t.local")
    db.add(colleague)
    db.flush()
    theirs = Document(
        workspace_id=workspace.id,
        uploaded_by_user_id=colleague.id,
        s3_key=f"ws/{workspace.id}/{uuid.uuid4()}-colleague.jpg",
        filename="colleague.jpg",
    )
    db.add(theirs)
    db.flush()

    # As an owner, a colleague's receipt is visible.
    assert api.get(f"/documents/{theirs.id}").status_code == 200

    membership.role = MembershipRole.employee
    db.flush()
    assert api.get(f"/documents/{theirs.id}").status_code == 404
    # Their own upload still works.
    own = presign(api)
    assert api.get(f"/documents/{own['document_id']}").status_code == 200


# --- confirm ---------------------------------------------------------------


def test_confirm_creates_one_asset_and_links_the_receipt(api: TestClient, db: Session) -> None:
    document_id = extracted_document(api)

    response = api.post(
        f"/documents/{document_id}/confirm", json={"assets": [asset_entry()]}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["created_asset_ids"]) == 1
    assert body["document_id"] == document_id

    asset = db.get(Asset, uuid.UUID(body["created_asset_ids"][0]))
    assert asset.name == "Dell Latitude 5540"
    # Linked to the receipt it came from, without the client having to say so.
    link = db.scalars(
        select(AssetDocument).where(
            AssetDocument.asset_id == asset.id,
            AssetDocument.document_id == uuid.UUID(document_id),
        )
    ).first()
    assert link is not None

    document = db.get(Document, uuid.UUID(document_id))
    assert document.status is DocumentStatus.confirmed
    # Raw OCR kept next to what the user approved, for the accuracy report.
    assert document.extracted_json is not None
    assert document.confirmed_json["created_asset_ids"] == body["created_asset_ids"]


def test_confirm_creates_several_assets_from_one_invoice(api: TestClient, db: Session) -> None:
    """The multi-line case: three laptops on one receipt become three assets."""
    document_id = extracted_document(api)

    response = api.post(
        f"/documents/{document_id}/confirm",
        json={
            "assets": [
                asset_entry(name="Laptop A", serial_number="SN-A"),
                asset_entry(name="Laptop B", serial_number="SN-B"),
                asset_entry(name="Mouse", serial_number="SN-C", price="590.00"),
            ]
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()["created_asset_ids"]
    assert len(created) == 3

    links = db.scalars(
        select(AssetDocument).where(AssetDocument.document_id == uuid.UUID(document_id))
    ).all()
    assert len(links) == 3


def test_confirm_before_extraction_is_a_conflict(api: TestClient) -> None:
    reserved = presign(api)
    response = api.post(
        f"/documents/{reserved['document_id']}/confirm", json={"assets": [asset_entry()]}
    )
    assert response.status_code == 409


def test_confirming_twice_is_a_conflict(api: TestClient) -> None:
    """Otherwise a double-tap on Save creates the assets a second time."""
    document_id = extracted_document(api)
    first = api.post(f"/documents/{document_id}/confirm", json={"assets": [asset_entry()]})
    assert first.status_code == 201
    second = api.post(f"/documents/{document_id}/confirm", json={"assets": [asset_entry(serial_number="OTHER")]})
    assert second.status_code == 409


def test_one_bad_entry_rejects_the_whole_invoice(api: TestClient, db: Session) -> None:
    """All or nothing, and the error says which row.

    A five-line invoice where line two has a duplicate serial must not leave
    line one behind with no clean way to retry.
    """
    document_id = extracted_document(api)
    api_response = api.post(
        f"/documents/{document_id}/confirm",
        json={
            "assets": [
                asset_entry(name="Good", serial_number="SN-GOOD"),
                asset_entry(name="Also good", serial_number="SN-GOOD"),  # duplicate
            ]
        },
    )
    assert api_response.status_code == 422, api_response.text
    # loc points at the offending entry, so the review screen marks that row.
    assert api_response.json()["detail"][0]["loc"][:3] == ["body", "assets", 1]

    # Nothing was created, including the entry that was fine.
    assert db.scalars(select(Asset).where(Asset.name == "Good")).first() is None
    document = db.get(Document, uuid.UUID(document_id))
    assert document.status is DocumentStatus.extracted


def test_confirm_requires_at_least_one_asset(api: TestClient) -> None:
    document_id = extracted_document(api)
    response = api.post(f"/documents/{document_id}/confirm", json={"assets": []})
    assert response.status_code == 422


def test_missing_vendor_names_the_field_and_the_row(api: TestClient) -> None:
    """Schema-level failures land in the same place as service-level ones."""
    document_id = extracted_document(api)
    entry = asset_entry()
    del entry["vendor_name"]
    response = api.post(f"/documents/{document_id}/confirm", json={"assets": [entry]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][:3] == ["body", "assets", 0]


# --- download (GitHub #95) ---------------------------------------------------


def _path_of(url: str) -> str:
    """The path and query of a dev link, so TestClient can follow it."""
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def test_download_opens_the_uploaded_file_under_its_name(api: TestClient) -> None:
    document = presign(api, filename="ใบเสร็จ Power Buy.jpg")
    upload(api, document["document_id"], b"the-receipt-bytes")

    response = api.get(f"/documents/{document['document_id']}/download")

    assert response.status_code == 200, response.text
    link = response.json()
    assert link["expires_in"] == settings.presigned_url_ttl_seconds
    assert "/dev-download?" in link["url"]

    # A new browser tab sends no auth headers; the signed link is enough.
    opened = TestClient(app).get(_path_of(link["url"]))
    assert opened.status_code == 200
    assert opened.content == b"the-receipt-bytes"
    assert opened.headers["content-type"] == "image/jpeg"
    disposition = opened.headers["content-disposition"]
    assert disposition.startswith("inline;")
    assert "filename*=UTF-8''%E0%B9%83%E0%B8%9A" in disposition


def test_download_before_upload_is_404(api: TestClient) -> None:
    document = presign(api)
    assert api.get(f"/documents/{document['document_id']}/download").status_code == 404


def test_download_follows_the_same_visibility_as_get(
    api: TestClient, db: Session, workspace: Workspace, other_workspace: Workspace,
    membership: Membership,
) -> None:
    theirs = Document(
        workspace_id=other_workspace.id,
        s3_key=f"ws/{other_workspace.id}/{uuid.uuid4()}-theirs.jpg",
        filename="theirs.jpg",
    )
    colleague = User(cognito_sub=f"other-{uuid.uuid4()}", email=f"o-{uuid.uuid4()}@t.local")
    db.add_all([theirs, colleague])
    db.flush()
    colleagues = Document(
        workspace_id=workspace.id,
        uploaded_by_user_id=colleague.id,
        s3_key=f"ws/{workspace.id}/{uuid.uuid4()}-colleague.jpg",
        filename="colleague.jpg",
    )
    db.add(colleagues)
    db.flush()
    storage.write_local(theirs.s3_key, b"x")
    storage.write_local(colleagues.s3_key, b"x")

    assert api.get(f"/documents/{theirs.id}/download").status_code == 404
    assert api.get(f"/documents/{colleagues.id}/download").status_code == 200

    membership.role = MembershipRole.employee
    db.flush()
    assert api.get(f"/documents/{colleagues.id}/download").status_code == 404


def test_a_tampered_or_expired_dev_link_is_refused(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = presign(api)
    upload(api, document["document_id"])
    url = _path_of(api.get(f"/documents/{document['document_id']}/download").json()["url"])
    anonymous = TestClient(app)

    assert anonymous.get(url.replace("signature=", "signature=0")).status_code == 403
    other_id = uuid.uuid4()
    assert anonymous.get(url.replace(document["document_id"], str(other_id))).status_code == 403

    later = time.time() + settings.presigned_url_ttl_seconds + 1
    monkeypatch.setattr(time, "time", lambda: later)
    assert anonymous.get(url).status_code == 403


def test_the_dev_download_route_is_off_on_s3(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    document = presign(api)
    upload(api, document["document_id"])
    url = _path_of(api.get(f"/documents/{document['document_id']}/download").json()["url"])

    monkeypatch.setattr(settings, "storage_backend", "s3")
    assert TestClient(app).get(url).status_code == 404


def test_the_s3_link_opens_inline_under_the_original_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """The overrides are signed into the presigned GET, not left to S3 metadata."""
    calls: list[dict] = []

    class FakeS3:
        def generate_presigned_url(self, operation: str, Params: dict, ExpiresIn: int) -> str:
            calls.append({"operation": operation, **Params})
            return "https://bucket.example/signed"

    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_bucket_name", "bucket")
    monkeypatch.setattr(storage, "_client", lambda: FakeS3())

    url = storage.presigned_get_url("k", filename='bad "name".pdf', content_type="application/pdf")

    assert url == "https://bucket.example/signed"
    assert calls[0]["operation"] == "get_object"
    assert calls[0]["ResponseContentType"] == "application/pdf"
    assert calls[0]["ResponseContentDisposition"] == (
        "inline; filename=\"bad _name_.pdf\"; filename*=UTF-8''bad%20%22name%22.pdf"
    )
