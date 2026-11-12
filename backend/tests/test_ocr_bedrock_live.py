"""Claude on Bedrock against a real receipt (CLOUDAPPG5-95).

**Skipped unless Bedrock is actually configured**: it needs OCR_BACKEND=bedrock,
BEDROCK_MODEL_ID, and AWS credentials that may call the model. It is the only
test that exercises the real service, so on CI and on a teammate's laptop it
simply does nothing.

Run it:

    docker compose exec \\
      -e OCR_BACKEND=bedrock -e BEDROCK_MODEL_ID=... -e BEDROCK_REGION=... \\
      -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... \\
      backend pytest tests/test_ocr_bedrock_live.py -m aws -s

or directly: `OCR_BACKEND=bedrock BEDROCK_MODEL_ID=... pytest tests/test_ocr_bedrock_live.py -m aws -s`

`-s` prints the parsed reading. Like the Textract live test, this asserts the
contract (shape, types, that something was read), not exact values: model
output shifts, and a test pinned to one vendor name would fail for reasons
that are not regressions. Compare the printed reading with the receipt by eye.
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import pytest

from app.core.config import settings
from app.services import ocr, storage

pytestmark = pytest.mark.aws

JIB_RECEIPT = Path(__file__).parent / "fixtures" / "receipts" / "jib-receipt.jpg"


def _unavailable() -> str | None:
    if settings.ocr_backend != "bedrock":
        return f"OCR_BACKEND is {settings.ocr_backend!r}, not 'bedrock'"
    if not settings.bedrock_model_id:
        return "BEDROCK_MODEL_ID is not set"
    if boto3.Session().get_credentials() is None:
        return "no AWS credentials available to boto3"
    return None


requires_bedrock = pytest.mark.skipif(_unavailable() is not None, reason=_unavailable() or "")

EXTRACTED_KEYS = {"vendor_name", "purchase_date", "total_amount", "currency", "line_items"}


def _check_contract(parsed: dict) -> None:
    assert set(parsed) == EXTRACTED_KEYS
    assert isinstance(parsed["line_items"], list)
    for item in parsed["line_items"]:
        assert set(item) == {"name", "serial_number", "price"}
    if parsed["purchase_date"] is not None:
        assert len(parsed["purchase_date"]) == 10 and parsed["purchase_date"][4] == "-"
    if parsed["total_amount"] is not None:
        assert parsed["total_amount"].count(".") == 1
    assert any(
        (parsed["vendor_name"], parsed["total_amount"], parsed["line_items"])
    ), "Bedrock returned nothing usable from this receipt"


@requires_bedrock
def test_bedrock_reads_the_jib_receipt() -> None:
    """One real Bedrock call, through our image prep, prompt and parser."""
    assert JIB_RECEIPT.exists(), f"missing fixture: {JIB_RECEIPT}"
    key = "live-test-jib-receipt.jpg"
    storage.write_local(key, JIB_RECEIPT.read_bytes())

    parsed = ocr.extract(key, "jib-receipt.jpg", "image/jpeg")
    print("\nparsed from jib-receipt.jpg:")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    _check_contract(parsed)


@requires_bedrock
def test_the_whole_upload_and_extract_path_against_bedrock(api, db) -> None:
    """The same receipt through presign -> upload -> submit, not just the parser."""
    reserved = api.post(
        "/documents/presign",
        json={"filename": "jib-receipt.jpg", "content_type": "image/jpeg"},
    ).json()
    api.put(
        f"/documents/{reserved['document_id']}/dev-upload",
        content=JIB_RECEIPT.read_bytes(),
    )
    response = api.post(f"/documents/{reserved['document_id']}/submit")
    assert response.status_code == 202, response.text
    body = response.json()
    print("\nstatus:", body["status"], "error:", body["error"])
    assert body["status"] == "extracted", body["error"]
