"""Receipt and invoice extraction (CLOUDAPPG5-95).

Amazon Textract's **AnalyzeExpense** is the right call here rather than plain
text detection: it already understands receipts, so it returns the vendor, the
date, the total and the line items as labelled fields instead of leaving us to
guess at them from a wall of text.

The useful, fragile part is `parse_expense_response()`, which turns Textract's
reply into the `extracted` shape in docs/api.md. It is a pure function, so it
is tested against a recorded response and needs neither AWS nor a database —
which matters, because every real receipt has its own way of writing a date.

Two backends, chosen by `OCR_BACKEND`:

* `textract` — the real thing.
* `fake` — canned fields, so the OCR Review screen (D07) can be built and
  demoed with no AWS account and no per-page charge.

**Known limitation** (documented in docs/architecture.md): extraction runs
in-process and synchronously, so a crash can strand a job in `processing`, and
a multi-page PDF needs Textract's async API, which this does not use yet.
`documents.attempts` and `updated_at` exist so a stuck job can be retried.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.services import storage

logger = logging.getLogger(__name__)


class OcrError(RuntimeError):
    """Extraction could not be completed. The document's `error` records it."""


# Textract's own field names. ITEM/PRICE/PRODUCT_CODE appear per line item,
# the rest in the document summary.
_VENDOR = "VENDOR_NAME"
_DATE = "INVOICE_RECEIPT_DATE"
_TOTAL = "TOTAL"
_CURRENCY = "CURRENCY"
_ITEM = "ITEM"
_PRICE = "PRICE"
_PRODUCT_CODE = "PRODUCT_CODE"

# Receipts write dates every way imaginable. Day-first before month-first:
# this is a Thai project, where 01/03/2025 is 1 March.
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%m/%d/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    "%d/%m/%y", "%Y/%m/%d",
)

_CURRENCY_SYMBOLS = {"฿": "THB", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}

_AMOUNT_CHARS = re.compile(r"[^0-9.,-]")
_THOUSANDS = re.compile(r",(?=\d{3}\b)")

_textract_client = None


def _client():
    global _textract_client
    if _textract_client is None:
        _textract_client = boto3.client("textract", region_name=settings.aws_region)
    return _textract_client


def _parse_date(text: str | None) -> str | None:
    """A receipt's date as `YYYY-MM-DD`, or None if it cannot be read.

    Returning None is a real answer: the review screen (D07) shows the field
    empty and the user types it. A wrong guess is worse than no guess, because
    the user would accept it without looking.
    """
    if not text:
        return None
    cleaned = " ".join(text.split())
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
        # A two-digit year can land a century out; anything far in the future
        # is a misread, not a purchase.
        if parsed.year < 1990 or parsed.year > date.today().year + 1:
            continue
        return parsed.isoformat()
    return None


def _parse_amount(text: str | None) -> str | None:
    """A money value as a plain decimal string, or None.

    Returned as a string, not a float: it goes into JSON and then into a
    NUMERIC column, and float would round money on the way through.
    """
    if not text:
        return None
    stripped = _AMOUNT_CHARS.sub("", _THOUSANDS.sub("", text))
    if not stripped or stripped in {"-", ".", "-."}:
        return None
    try:
        amount = Decimal(stripped)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    return f"{amount:.2f}"


def _sniff_currency(*texts: str | None) -> str | None:
    """The currency from a symbol or code in the amount text.

    Textract only sometimes returns a CURRENCY field, and the total usually
    carries the symbol anyway ("฿32,900.00").
    """
    for text in texts:
        if not text:
            continue
        upper = text.upper()
        for code in ("THB", "USD", "EUR", "GBP", "JPY"):
            if code in upper:
                return code
        for symbol, code in _CURRENCY_SYMBOLS.items():
            if symbol in text:
                return code
    return None


def _field_text(fields: list[dict[str, Any]], wanted: str) -> str | None:
    """The value of one labelled field, preferring the most confident reading."""
    matches = [
        field
        for field in fields
        if (field.get("Type") or {}).get("Text") == wanted
        and (field.get("ValueDetection") or {}).get("Text")
    ]
    if not matches:
        return None
    best = max(
        matches,
        key=lambda f: (f.get("ValueDetection") or {}).get("Confidence") or 0,
    )
    return (best["ValueDetection"]["Text"] or "").strip() or None


def parse_expense_response(response: dict[str, Any]) -> dict[str, Any]:
    """Textract's AnalyzeExpense reply -> the `extracted` shape in docs/api.md.

    Every field is optional. A receipt photographed at an angle in bad light
    gives up some of them, and the review screen is built to be filled in by
    hand — so a missing field is normal, not an error. Only a response with no
    expense document at all is a failure.
    """
    documents = response.get("ExpenseDocuments") or []
    if not documents:
        raise OcrError("Textract returned no expense document for this file.")

    summary = documents[0].get("SummaryFields") or []
    total_text = _field_text(summary, _TOTAL)

    line_items: list[dict[str, Any]] = []
    for group in documents[0].get("LineItemGroups") or []:
        for item in group.get("LineItems") or []:
            fields = item.get("LineItemExpenseFields") or []
            name = _field_text(fields, _ITEM)
            price = _parse_amount(_field_text(fields, _PRICE))
            # PRODUCT_CODE is the closest Textract gets to a serial number.
            # Often absent, which is why the review screen makes the user
            # supply it — the serial is required on an asset.
            serial = _field_text(fields, _PRODUCT_CODE)
            if not any((name, price, serial)):
                continue
            line_items.append(
                {"name": name, "serial_number": serial, "price": price}
            )

    return {
        "vendor_name": _field_text(summary, _VENDOR),
        "purchase_date": _parse_date(_field_text(summary, _DATE)),
        "total_amount": _parse_amount(total_text),
        "currency": _field_text(summary, _CURRENCY) or _sniff_currency(total_text),
        "line_items": line_items,
    }


def _fake_extraction(filename: str | None) -> dict[str, Any]:
    """Canned fields for `OCR_BACKEND=fake`.

    Deliberately not a perfect reading: the date is missing and one line item
    has no serial number, because that is what a real receipt does and it is
    what the review screen has to cope with. A fake that always returns
    complete data hides every gap in the UI.
    """
    return {
        "vendor_name": "Power Buy",
        "purchase_date": None,
        "total_amount": "32900.00",
        "currency": "THB",
        "line_items": [
            {
                "name": "Dell Latitude 5540",
                "serial_number": "ABC123",
                "price": "32900.00",
            },
            {"name": "Laptop sleeve", "serial_number": None, "price": "890.00"},
        ],
        "_source": f"fake OCR backend, file {filename or 'unknown'}",
    }


def extract(s3_key: str, filename: str | None, content_type: str | None) -> dict[str, Any]:
    """Read one uploaded file. Raises OcrError; the caller records it.

    On the `textract` backend with S3 storage, Textract is pointed at the
    object rather than handed the bytes — one less copy of the file over the
    wire, and no need for the API to hold a 10MB scan in memory.
    """
    if settings.ocr_backend == "fake":
        return _fake_extraction(filename)

    if settings.storage_backend == "s3":
        document = {
            "S3Object": {"Bucket": settings.s3_bucket_name, "Name": s3_key}
        }
    else:
        document = {"Bytes": storage.read_bytes(s3_key)}

    try:
        response = _client().analyze_expense(Document=document)
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - needs AWS
        logger.warning("Textract failed for %s: %s", s3_key, exc)
        raise OcrError(f"Textract could not read this file: {exc}") from exc

    return parse_expense_response(response)
