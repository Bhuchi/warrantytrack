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

* `textract` — Amazon Textract AnalyzeExpense.
* `bedrock` — a Claude model on Amazon Bedrock reads the image and returns
  JSON. Handles Thai and photos well; images and PDFs. Scored in
  scripts/ocr_compare.
* `fake` — canned fields, so the OCR Review screen (D07) can be built and
  demoed with no AWS account and no per-page charge.

**Known limitation** (documented in docs/architecture.md): extraction runs
in-process and synchronously, so a crash can strand a job in `processing`, and
a multi-page PDF needs Textract's async API, which this does not use yet.
`documents.attempts` and `updated_at` exist so a stuck job can be retried.
"""

from __future__ import annotations

import io
import json
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


class NotAReceipt(OcrError):
    """The file was read fine, but it is not an invoice or a receipt.

    A subclass of OcrError on purpose: the caller already records an OcrError
    as `failed` with `str(error)` for the review screen, and that message is
    written to be shown to the person who picked the wrong file.
    """

    def __init__(self) -> None:
        super().__init__(
            "This doesn't look like an invoice or receipt. "
            "Please upload only an invoice or receipt."
        )


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


# --- Model-based backends ----------------------------------------------------


def _parse_ocr_date(text: str) -> str | None:
    """`_parse_date`, plus Thai Buddhist-era years (2568 -> 2025)."""
    found = _parse_date(text)
    if found:
        return found
    match = re.search(r"(?<!\d)(25\d{2})(?!\d)", text)
    if match:
        return _parse_date(text.replace(match.group(1), str(int(match.group(1)) - 543)))
    return None


# Warranty length ("3-Y", "2 YEAR", "1 ปี") and "*P25"-style promo or shop codes
# that receipts print inside the product line. They belong to other fields (or
# to nothing), not to the product name.
_NAME_NOISE = re.compile(
    r"(?<![\w])\d{1,2}\s?-?\s?(?:Y|YR|YRS|YEAR|YEARS|ปี)(?![\w])"
    r"|(?<!\w)\*\w+",
    re.IGNORECASE,
)


def _clean_product_name(name: str | None) -> str | None:
    """The product name without warranty or promo markers; the original if that would leave nothing."""
    if not name:
        return name
    cleaned = re.sub(r"\s{2,}", " ", _NAME_NOISE.sub(" ", name)).strip(" -,;/")
    return cleaned or name


def _clean_invoice_number(value: str | None) -> str | None:
    """The invoice number as one tidy token string, or None.

    Drops a leading label the model may have copied ("Invoice No: INV-1"),
    collapses whitespace, and refuses anything implausibly long, which is a
    sentence or a barcode run rather than a number.
    """
    value = (value or "").strip()
    if not value:
        return None
    # Only whole words, and only when a separator follows, so "INV-2025-001"
    # and "Invoice-7" are left alone.
    cleaned = re.sub(
        r"^(?:tax\s+)?(?:invoice|receipt)(?:\s*(?:no\.?|number|#))?(?=[\s:#.]|$)\s*[:#.]*\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :#.")
    return cleaned if 0 < len(cleaned) <= 40 else None


def _clean_category(value: str | None) -> str | None:
    """A short category label, or None. Length-capped like the catalog's name column."""
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:60] if cleaned else None


def _parse_months(value: Any) -> int | None:
    """A warranty length in whole months, or None.

    The model is told to answer in months, but a bad answer ("3 years", 0,
    999, true) must become an empty Duration field rather than a wrong one the
    user accepts without looking. 120 months (10 years) is a generous ceiling.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            return None
    try:
        months = int(value)
    except (TypeError, ValueError):
        return None
    return months if 1 <= months <= 120 else None


def parse_model_json(data: dict[str, Any]) -> dict[str, Any]:
    """A model's JSON -> the `extracted` shape, re-validating every value.

    The model is asked for clean values but is not trusted: dates and amounts
    go back through the same parsers as the other backends, so a malformed
    answer becomes an empty field instead of bad data in the review screen.
    """
    if not isinstance(data, dict):
        raise OcrError("The model returned an unexpected answer.")

    # Only an explicit "no" rejects the file. A missing or unclear answer is
    # treated as a receipt, so a blurry real receipt is never turned away; the
    # review screen is where a person fixes what could not be read.
    if data.get("is_receipt") is False or str(data.get("is_receipt")).strip().lower() == "false":
        raise NotAReceipt()

    def text(value: Any) -> str | None:
        return str(value).strip() or None if value is not None else None

    items = []
    for item in data.get("line_items") or []:
        if not isinstance(item, dict):
            continue
        name = _clean_product_name(text(item.get("name")))
        serial = text(item.get("serial_number"))
        price = _parse_amount(text(item.get("price")))
        if any((name, serial, price)):
            items.append({
                "name": name,
                "serial_number": serial,
                "price": price,
                "warranty_months": _parse_months(item.get("warranty_months")),
                "category": _clean_category(text(item.get("category"))),
            })

    total_text = text(data.get("total_amount"))
    currency = text(data.get("currency"))
    return {
        "vendor_name": text(data.get("vendor_name")),
        "purchase_date": _parse_ocr_date(text(data.get("purchase_date")) or ""),
        "invoice_number": _clean_invoice_number(text(data.get("invoice_number"))),
        "total_amount": _parse_amount(total_text),
        "currency": currency.upper() if currency else _sniff_currency(total_text),
        "line_items": items,
    }


# --- Bedrock ---------------------------------------------------------------

# The prompt that scripts/ocr_compare scored; change it there first, then here.
_BEDROCK_SYSTEM_PROMPT = """You extract data from a purchase receipt or invoice. It may be in Thai, English, or both.

Return ONLY one JSON object, no prose and no markdown, with exactly these keys:
{
  "is_receipt": boolean,
  "vendor_name": string | null,
  "purchase_date": "YYYY-MM-DD" | null,
  "invoice_number": string | null,
  "total_amount": string | null,
  "currency": string | null,
  "line_items": [
    {"name": string | null, "price": string | null,
     "serial_number": string | null, "warranty_months": integer | null,
     "category": string | null}
  ]
}

Rules:
- is_receipt: true when the document is a purchase receipt, invoice, tax invoice
  or order confirmation that shows something bought, even if it is blurry or
  partly unreadable. false for anything else, such as a photo of a product or a
  room, a screenshot of an app, an ID card, a form, a letter or a blank page.
  When it is false, set every other key to null and line_items to [].
- Use null for anything you cannot read with confidence. Never guess: an empty
  field is better than a wrong one.
- purchase_date: the purchase / issue date. Dates are day-first (01/03/2025 is
  1 March 2025). Thai receipts may use Buddhist Era years such as 2568 - convert
  to Gregorian by subtracting 543. Ignore dates that belong to an address, a tax
  ID, a document number or a due date.
- invoice_number: the number that identifies this document. Prefer an invoice /
  receipt / tax invoice number, printed beside a label such as "Invoice No.",
  "Receipt No.", "Tax Invoice", "เลขที่ใบกำกับภาษี", "เลขที่ใบเสร็จ" or "เลขที่".
  If the document has none, because it is itself an online order or purchase
  order (ใบสั่งซื้อสินค้า, "Order No."), use its own order number
  ("เลขที่ใบสั่งซื้อ"). Return only the number, without the label. It is NEVER
  the 13-digit tax ID, a phone number, a bank account number, a product or item
  code, a queue or member number, or a barcode value that belongs to a product.
- total_amount: the final amount paid, as a plain decimal string without
  thousands separators, e.g. "37570.00".
- currency: ISO code. THB for ฿ or บาท.
- vendor_name: the shop's name as printed in the logo or header.
- line_items: one entry per purchased product. price is that line's total
  amount as a decimal string.
- name: ONLY the product's own name, brand and model, e.g. "CPU AMD AM5 RYZEN
  7500F". Leave out everything else printed on that line: the warranty length
  ("3-Y", "1 YEAR", "ประกัน 1 ปี" - that goes in warranty_months), promo or
  shop codes such as "*P25", quantities, item numbers, SKUs and barcodes.
- serial_number: ONLY when printed with an explicit label such as S/N, SN or
  Serial. Product codes, SKUs, barcodes and item numbers are NOT serial numbers.
- category: what kind of product the item is. Choose ONE of: Laptop, Desktop,
  Computer Component, Monitor, Phone, Tablet, Printer, Camera, Network
  Equipment, Accessory, Appliance, Furniture, Other. Use Computer Component for
  parts such as CPU, GPU, RAM, SSD, motherboard or a power supply, and Other
  when none fits. Never invent a new label.
- warranty_months: the warranty length in months if it is printed for that
  item ("3-Y" or "3 YEAR" is 36, "ประกัน 1 ปี" is 12). null if not printed,
  and null for lifetime warranties."""

_bedrock_client = None
_MAX_IMAGE_SIDE = 2000  # Bedrock limits image size; a smaller image is cheaper too.


def _bedrock():
    global _bedrock_client
    if _bedrock_client is None:
        from botocore.config import Config

        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.bedrock_region or settings.aws_region,
            config=Config(read_timeout=120, retries={"max_attempts": 3, "mode": "standard"}),
        )
    return _bedrock_client


def _prepare_image(data: bytes) -> bytes:
    """JPEG bytes with the long side capped, upright regardless of EXIF."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except UnidentifiedImageError as exc:
        raise OcrError("This file is not an image the OCR can read.") from exc
    longest = max(image.size)
    if longest > _MAX_IMAGE_SIDE:
        scale = _MAX_IMAGE_SIDE / longest
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def _json_from_reply(reply: str) -> dict[str, Any]:
    """The JSON object in a model reply, tolerating a ```json fence."""
    text = reply.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise OcrError("The model did not return valid JSON.") from exc


def _bedrock_extract(s3_key: str, filename: str | None, content_type: str | None) -> dict[str, Any]:
    if not settings.bedrock_model_id:
        raise OcrError("OCR_BACKEND=bedrock but BEDROCK_MODEL_ID is not set.")

    data = storage.read_bytes(s3_key)
    is_pdf = (
        data[:4] == b"%PDF"
        or content_type == "application/pdf"
        or (filename or "").lower().endswith(".pdf")
    )
    if is_pdf:
        # Converse reads a PDF natively (text and page images), so there is
        # nothing to render here. The name is fixed on purpose: the API only
        # allows a narrow character set and a user's filename can hold
        # anything, including prompt text.
        attachment = {"document": {"format": "pdf", "name": "receipt", "source": {"bytes": data}}}
        request_text = "Extract the receipt in this document."
    else:
        attachment = {"image": {"format": "jpeg", "source": {"bytes": _prepare_image(data)}}}
        request_text = "Extract the receipt in this image."

    try:
        response = _bedrock().converse(
            modelId=settings.bedrock_model_id,
            system=[{"text": _BEDROCK_SYSTEM_PROMPT}],
            messages=[{
                "role": "user",
                "content": [
                    attachment,
                    {"text": request_text},
                ],
            }],
            # No temperature: some current models reject it as deprecated.
            inferenceConfig={"maxTokens": 3000},
        )
        blocks = response["output"]["message"]["content"]
    except (BotoCoreError, ClientError, KeyError) as exc:  # pragma: no cover - needs AWS
        # The exception class (NoCredentialsError, AccessDeniedException,
        # ValidationException ...) says what to fix and carries no secret, so
        # it goes in the message the review screen shows. The full text is
        # logged for whoever has the server logs.
        logger.warning("Bedrock failed for %s: %s: %s", s3_key, type(exc).__name__, exc)
        code = exc.response.get("Error", {}).get("Code") if isinstance(exc, ClientError) else None
        raise OcrError(f"Bedrock could not read this file ({code or type(exc).__name__}).") from exc

    return parse_model_json(_json_from_reply("".join(b.get("text", "") for b in blocks)))


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
        "invoice_number": "INV-2025-001",
        "total_amount": "32900.00",
        "currency": "THB",
        "line_items": [
            {
                "name": "Dell Latitude 5540",
                "serial_number": "ABC123",
                "price": "32900.00",
                "warranty_months": 36,
                "category": "Laptop",
            },
            {
                "name": "Laptop sleeve",
                "serial_number": None,
                "price": "890.00",
                "warranty_months": None,
                "category": "Accessory",
            },
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

    if settings.ocr_backend == "bedrock":
        return _bedrock_extract(s3_key, filename, content_type)

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
