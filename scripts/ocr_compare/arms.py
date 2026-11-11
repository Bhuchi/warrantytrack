"""The three ways of reading a receipt.

  a  Tesseract text  -> regex parser                  (no AWS)
  b  Claude on Bedrock reads the image directly       (AWS)
  c  Tesseract text  -> Claude on Bedrock (text only) (AWS)

Heavy imports (PIL, pytesseract, boto3) happen inside the functions, so
`--arms a` runs without AWS and the unit tests need none of them.

A vs C shows what a good parser is worth on the same OCR text.
C vs B shows what Tesseract's OCR costs you compared with Claude seeing the image.
"""

from __future__ import annotations

import io
import time
from typing import Any

ARM_NAMES = {
    "a": "Tesseract + regex",
    "b": "Claude vision",
    "c": "Tesseract text -> Claude",
}

SYSTEM_PROMPT = """You extract data from a purchase receipt or invoice. It may be in Thai, English, or both.

Return ONLY one JSON object, no prose and no markdown, with exactly these keys:
{
  "vendor_name": string | null,
  "purchase_date": "YYYY-MM-DD" | null,
  "total_amount": string | null,
  "currency": string | null,
  "line_items": [
    {"name": string | null, "price": string | null,
     "serial_number": string | null, "warranty_months": integer | null}
  ]
}

Rules:
- Use null for anything you cannot read with confidence. Never guess: an empty
  field is better than a wrong one.
- purchase_date: the purchase / issue date. Dates are day-first (01/03/2025 is
  1 March 2025). Thai receipts may use Buddhist Era years such as 2568 — convert
  to Gregorian by subtracting 543. Ignore dates that belong to an address, a tax
  ID, a document number or a due date.
- total_amount: the final amount paid, as a plain decimal string without
  thousands separators, e.g. "37570.00".
- currency: ISO code. THB for ฿ or บาท.
- vendor_name: the shop's name as printed in the logo or header.
- line_items: one entry per purchased product, as printed. price is that line's
  total amount as a decimal string.
- serial_number: ONLY when printed with an explicit label such as S/N, SN or
  Serial. Product codes, SKUs, barcodes and item numbers are NOT serial numbers.
- warranty_months: the warranty length in months if it is printed for that
  item ("3-Y" or "3 YEAR" is 36, "ประกัน 1 ปี" is 12). null if not printed,
  and null for lifetime warranties."""

_USER_IMAGE = "Extract the receipt in this image."
_USER_TEXT = (
    "Below is raw OCR text of a receipt. It may contain misreadings, especially of "
    "Thai text. Extract the receipt.\n\n--- OCR TEXT ---\n{text}\n--- END ---"
)


def tesseract_text(path: str, lang: str = "tha+eng", psm: int = 6) -> str:
    """Raw Tesseract text, after the usual cleanup (greyscale, contrast, upscale)."""
    import pytesseract
    from PIL import Image, ImageOps

    available = pytesseract.get_languages(config="")
    missing = [code for code in lang.split("+") if code not in available]
    if missing:
        raise RuntimeError(
            f"Tesseract language data missing: {', '.join(missing)}. "
            "On macOS: brew install tesseract tesseract-lang"
        )

    image = ImageOps.exif_transpose(Image.open(path)).convert("L")
    image = ImageOps.autocontrast(image)
    if image.width < 1600:  # Tesseract reads small print badly
        scale = 1600 / image.width
        image = image.resize((1600, int(image.height * scale)), Image.LANCZOS)
    return pytesseract.image_to_string(image, lang=lang, config=f"--psm {psm}")


def prepare_image(path: str, max_side: int = 2000) -> tuple[bytes, str]:
    """JPEG bytes for Bedrock, with the long side capped.

    Phone photos are several MB; Bedrock limits image size, and a smaller image
    is also cheaper. The cap is a choice made here, not a documented limit.
    """
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    longest = max(image.size)
    if longest > max_side:
        scale = max_side / longest
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue(), "jpeg"


def bedrock_client(region: str):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(read_timeout=120, retries={"max_attempts": 3, "mode": "standard"}),
    )


def _converse(
    client: Any, model_id: str, content: list[dict], temperature: float | None
) -> dict[str, Any]:
    inference: dict[str, Any] = {"maxTokens": 3000}
    if temperature is not None:
        inference["temperature"] = temperature
    started = time.perf_counter()
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": content}],
        inferenceConfig=inference,
    )
    blocks = response["output"]["message"]["content"]
    usage = response.get("usage", {})
    return {
        "raw": "".join(block.get("text", "") for block in blocks),
        "seconds": time.perf_counter() - started,
        "tokens_in": usage.get("inputTokens"),
        "tokens_out": usage.get("outputTokens"),
    }


def bedrock_vision(
    client: Any, model_id: str, path: str, max_side: int, temperature: float | None
) -> dict[str, Any]:
    image_bytes, fmt = prepare_image(path, max_side)
    content = [
        {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
        {"text": _USER_IMAGE},
    ]
    return _converse(client, model_id, content, temperature)


def bedrock_text(
    client: Any, model_id: str, ocr_text: str, temperature: float | None
) -> dict[str, Any]:
    content = [{"text": _USER_TEXT.format(text=ocr_text)}]
    return _converse(client, model_id, content, temperature)
