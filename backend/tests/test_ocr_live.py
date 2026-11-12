"""Textract against a real receipt (CLOUDAPPG5-95, groundwork for -102).

**Skipped unless AWS is actually configured.** It needs `OCR_BACKEND=textract`
and working credentials, so it does nothing on CI and nothing on a teammate's
machine — but it is the only test that exercises the real API, and it is what
the OCR accuracy numbers for the final presentation come from.

Run it once the account exists:

    docker compose exec \\
      -e OCR_BACKEND=textract \\
      -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... \\
      backend pytest tests/test_ocr_live.py -m aws -s

`-s` because the parsed result is printed: when a field comes back wrong, the
fix belongs in `parse_expense_response`, and seeing the whole reading is how
you know which one to look at.

Note it does **not** assert exact values. OCR output shifts with the model, the
photo and the lighting, so a test pinned to "vendor_name == 'JIB'" would start
failing for reasons that are not regressions. It asserts the contract — the
shape, the types, and that something was read — and prints the rest for a human.
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import pytest

from app.core.config import settings
from app.services import ocr

pytestmark = pytest.mark.aws

RECEIPTS = Path(__file__).parent / "fixtures" / "receipts"
JIB_RECEIPT = RECEIPTS / "jib-receipt.jpg"


def _aws_unavailable() -> str | None:
    """Why this cannot run, or None if it can."""
    if settings.ocr_backend != "textract":
        return f"OCR_BACKEND is {settings.ocr_backend!r}, not 'textract'"
    if boto3.Session().get_credentials() is None:
        return "no AWS credentials available to boto3"
    return None


requires_aws = pytest.mark.skipif(
    _aws_unavailable() is not None, reason=_aws_unavailable() or ""
)


@requires_aws
def test_textract_reads_the_jib_receipt() -> None:
    """One real AnalyzeExpense call, on a real receipt, through our parser."""
    assert JIB_RECEIPT.exists(), f"missing fixture: {JIB_RECEIPT}"

    client = boto3.client("textract", region_name=settings.aws_region)
    response = client.analyze_expense(
        Document={"Bytes": JIB_RECEIPT.read_bytes()}
    )

    parsed = ocr.parse_expense_response(response)
    print("\nparsed from jib-receipt.jpg:")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))

    # The contract, not the content.
    assert set(parsed) == {
        "vendor_name",
        "purchase_date",
        "total_amount",
        "currency",
        "line_items",
    }
    assert isinstance(parsed["line_items"], list)
    for item in parsed["line_items"]:
        assert set(item) == {"name", "serial_number", "price"}

    # A date and a total that parsed at all must be in our normalised form,
    # because that is what the review screen and the NUMERIC column expect.
    if parsed["purchase_date"] is not None:
        assert len(parsed["purchase_date"]) == 10 and parsed["purchase_date"][4] == "-"
    if parsed["total_amount"] is not None:
        assert parsed["total_amount"].count(".") == 1

    # Something was read. A reply where every field is empty means either the
    # photo is unusable or the parser is dropping fields — both worth failing.
    assert any(
        (parsed["vendor_name"], parsed["total_amount"], parsed["line_items"])
    ), "Textract returned nothing usable from this receipt"


@requires_aws
def test_the_whole_upload_and_extract_path_against_textract(api, db) -> None:
    """The same receipt through presign -> upload -> submit, not just the parser.

    Proves the plumbing as well as the reading: the bytes we store are the
    bytes Textract gets.
    """
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
