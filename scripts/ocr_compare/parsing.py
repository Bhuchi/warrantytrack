"""Pure helpers shared by the OCR arms and the scorer.

Nothing here touches AWS, Tesseract or the filesystem, so it is unit-tested
(test_ocr_compare.py) and safe to import anywhere.

Everything produces the same shape — the `extracted` object in docs/api.md:

    {
      "vendor_name": str | None,
      "purchase_date": "YYYY-MM-DD" | None,
      "total_amount": "37570.00" | None,
      "currency": "THB" | None,
      "line_items": [
        {"name": str | None, "price": "4590.00" | None,
         "serial_number": str | None, "warranty_months": int | None}
      ],
    }

An empty field is a real answer: a wrong guess is worse than none, because the
user accepts a prefilled value without looking.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

_DMY = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})(?!\d)")
_YMD = re.compile(r"(?<!\d)(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?!\d)")

# A money amount that has decimals: 37,570.00 or 4590.00. Requiring a decimal
# point keeps quantities, item codes and phone numbers out. One decimal digit is
# accepted because receipt photos often lose the last "0" at the paper's edge
# ("4,590.00" read as "4,590.0").
_AMT = r"(?:\d{1,3}(?:,\d{3})+\.\d{1,2}|\d+\.\d{1,2})"
_AMOUNT = re.compile(rf"(?<![\d.,])({_AMT})(?!\d)")

_WARRANTY = (
    (re.compile(r"(?<![A-Za-z0-9])(\d{1,2})\s*-?\s*(?:Y|YR|YRS|YEARS?)(?![A-Za-z])", re.I), 12),
    (re.compile(r"(\d{1,2})\s*ปี"), 12),
    (re.compile(r"(?<![A-Za-z0-9])(\d{1,3})\s*-?\s*(?:MONTHS?|MOS)(?![A-Za-z])", re.I), 1),
    (re.compile(r"(\d{1,3})\s*เดือน"), 1),
)

_TOTAL_KEYS = (
    "รวมทั้งสิ้น", "ราคารวม", "ยอดรวม", "ยอดสุทธิ", "สุทธิ", "รวมเงิน",
    "grand total", "net total", "amount due", "balance due", "total",
)
_NOT_TOTAL = ("subtotal", "sub total", "vat", "ภาษี", "change", "เงินทอน")
_DATE_KEYS = ("วันที่", "date")


def _digits(text: str) -> str:
    return text.translate(_THAI_DIGITS)


def _to_gregorian(year: int) -> int:
    """Two-digit years are 20xx; Buddhist Era years (2569) become 2026."""
    if year < 100:
        year += 2000
    if year >= 2400:
        year -= 543
    return year


def _valid(year: int, month: int, day: int, today: date) -> str | None:
    # Anything before 1990 or after next year is a misread, not a purchase.
    if year < 1990 or year > today.year + 1:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def find_dates(text: str | None, today: date | None = None) -> list[str]:
    """Every plausible date in `text`, as ISO strings, in reading order.

    Day-first (this is a Thai project: 01/03/2025 is 1 March) and Buddhist
    Era aware.
    """
    if not text:
        return []
    today = today or date.today()
    text = _digits(text)
    found: list[tuple[int, str]] = []
    for m in _DMY.finditer(text):
        iso = _valid(_to_gregorian(int(m.group(3))), int(m.group(2)), int(m.group(1)), today)
        if iso:
            found.append((m.start(), iso))
    for m in _YMD.finditer(text):
        iso = _valid(_to_gregorian(int(m.group(1))), int(m.group(2)), int(m.group(3)), today)
        if iso:
            found.append((m.start(), iso))
    return [iso for _, iso in sorted(found)]


def parse_date(text: str | None, today: date | None = None) -> str | None:
    dates = find_dates(text, today)
    return dates[0] if dates else None


def parse_amount(text: Any) -> str | None:
    """A money value as a plain decimal string ("37570.00"), or None."""
    if text is None:
        return None
    cleaned = re.sub(r"[^0-9.,\-]", "", re.sub(r",(?=\d{3}\b)", "", _digits(str(text))))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    return f"{amount:.2f}"


def parse_months(text: str | None) -> int | None:
    """Warranty length in months from item text: "3-Y", "2 YEARS", "ประกัน 1 ปี"."""
    if not text:
        return None
    text = _digits(text)
    for pattern, factor in _WARRANTY:
        m = pattern.search(text)
        if m:
            months = int(m.group(1)) * factor
            return months if 0 < months <= 600 else None
    return None


# --------------------------------------------------------------------------- #
# Arm A: a deliberately simple baseline parser for raw Tesseract text.
# --------------------------------------------------------------------------- #

_CODE_LINE = re.compile(rf"^\s*([A-Za-z0-9\-]{{6,}})\s+[\d,]+(?:\.\d+)?\s+\d+\s+({_AMT})\s*$")
_NAME_AMT = re.compile(rf"^\s*(?:[A-Za-z0-9\-]{{6,}}\s+)?(.*?\S)\s+({_AMT})\s*$")
_ENDS_WITH_AMT = re.compile(rf"{_AMT}\s*$")


def _has_letters(line: str, minimum: int = 3) -> bool:
    return sum(ch.isalpha() for ch in line) >= minimum


def _is_total_line(low: str) -> bool:
    return any(k in low for k in _TOTAL_KEYS) and not any(k in low for k in _NOT_TOTAL)


def _is_footer(line: str) -> bool:
    """The first total, subtotal or VAT line with an amount ends the item list.

    A header such as "ใบกำกับภาษี" mentions tax but has no amount, so it does
    not count.
    """
    low = line.lower()
    if _is_total_line(low):
        return True
    return any(k in low for k in _NOT_TOTAL) and bool(_ENDS_WITH_AMT.search(line))


def extract_baseline(text: str) -> dict[str, Any]:
    """Regex field extraction from raw OCR text.

    This is the "Tesseract only" arm. It is intentionally plain, so the result
    shows what you get from OCR text plus ordinary string handling. Two
    receipt layouts are understood for line items: `name ... amount` on one
    line, and a `code  price  qty  amount` line followed by a description
    line (the JIB layout).
    """
    # OCR often adds stray "|" and "[" where it sees table borders.
    lines = [ln.strip(" \t|[]") for ln in _digits(text or "").splitlines()]
    lines = [ln for ln in lines if ln]

    vendor = next((ln.strip() for ln in lines if _has_letters(ln)), None)

    date_lines = [ln for ln in lines if any(k in ln.lower() for k in _DATE_KEYS)]
    purchase_date = None
    for source in ("\n".join(date_lines), "\n".join(lines)):
        purchase_date = parse_date(source)
        if purchase_date:
            break

    total_amounts: list[Decimal] = []
    for ln in lines:
        if _is_total_line(ln.lower()):
            total_amounts += [Decimal(a.replace(",", "")) for a in _AMOUNT.findall(ln)]
    total = f"{max(total_amounts):.2f}" if total_amounts else None

    items: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_footer(line):
            break  # everything after this is the totals block
        code = _CODE_LINE.match(line)
        if code:
            desc: list[str] = []
            j = i + 1
            while (
                j < len(lines)
                and len(desc) < 2
                and not _CODE_LINE.match(lines[j])
                and not _ENDS_WITH_AMT.search(lines[j])
                and not _is_footer(lines[j])
            ):
                desc.append(lines[j].strip())
                j += 1
            name = " ".join(desc) or code.group(1)
            items.append(_item(name, code.group(2)))
            i = j
            continue
        named = _NAME_AMT.match(line)
        if named and _has_letters(named.group(1)):
            items.append(_item(named.group(1), named.group(2)))
        i += 1

    return {
        "vendor_name": vendor,
        "purchase_date": purchase_date,
        "total_amount": total,
        "currency": "THB" if re.search(r"฿|บาท|\bTHB\b", text or "") else None,
        "line_items": items,
    }


def _item(name: str, amount: str) -> dict[str, Any]:
    return {
        "name": name.strip(),
        "price": parse_amount(amount),
        "serial_number": None,  # a baseline cannot tell a serial from a SKU
        "warranty_months": parse_months(name),
    }


# --------------------------------------------------------------------------- #
# Arms B and C: validate what the model returned.
# --------------------------------------------------------------------------- #

def normalize_llm_json(raw: str) -> dict[str, Any]:
    """The model's reply -> the common shape, re-validated.

    The model is told to return null instead of guessing, but it is not
    trusted: dates and amounts go through the same parsers as everything
    else, so a malformed value becomes None rather than reaching the user.
    Raises ValueError if there is no JSON object at all.
    """
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the model output")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")

    def clean_str(value: Any) -> str | None:
        value = None if value is None else str(value).strip()
        return value or None

    currency = clean_str(data.get("currency"))
    items: list[dict[str, Any]] = []
    for item in data.get("line_items") or []:
        if not isinstance(item, dict):
            continue
        months = item.get("warranty_months")
        try:
            months = int(months) if months is not None else None
        except (TypeError, ValueError):
            months = None
        if months is not None and not 0 < months <= 600:
            months = None
        items.append(
            {
                "name": clean_str(item.get("name")),
                "price": parse_amount(item.get("price")),
                "serial_number": clean_str(item.get("serial_number")),
                "warranty_months": months,
            }
        )

    return {
        "vendor_name": clean_str(data.get("vendor_name")),
        "purchase_date": parse_date(clean_str(data.get("purchase_date"))),
        "total_amount": parse_amount(data.get("total_amount")),
        "currency": currency.upper() if currency and len(currency) == 3 else None,
        "line_items": items,
    }
