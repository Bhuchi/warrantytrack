"""Tests for the pure parts of the OCR comparison: parsing and scoring.

Run:  cd scripts/ocr_compare && python -m pytest -q
"""

from datetime import date

import pytest

import parsing
import scoring

TODAY = date(2026, 11, 10)


# ----------------------------------------------------------------- dates ---

@pytest.mark.parametrize(
    "text, expected",
    [
        ("IS00186 วันที่ : 23/08/2026 11:50", "2026-08-23"),
        ("23/08/2569", "2026-08-23"),          # Buddhist Era
        ("๒๓/๐๘/๒๕๖๙", "2026-08-23"),          # Thai digits and Buddhist Era
        ("01/03/25", "2025-03-01"),            # day-first, two-digit year
        ("2025-03-01", "2025-03-01"),
        ("99/99/2026", None),                  # not a date
        ("01/01/2035", None),                  # implausibly far ahead
        ("no date here", None),
    ],
)
def test_parse_date(text, expected):
    assert parsing.parse_date(text, TODAY) == expected


def test_find_dates_keeps_reading_order():
    text = "garbled 01/11/2017 12130\nวันที่ 23/08/2026"
    assert parsing.find_dates(text, TODAY) == ["2017-11-01", "2026-08-23"]


# --------------------------------------------------------------- amounts ---

@pytest.mark.parametrize(
    "text, expected",
    [("37,570.00", "37570.00"), ("฿32,900", "32900.00"), ("4590.5", "4590.50"),
     ("๑,๒๐๐.๐๐", "1200.00"), ("", None), (None, None), ("-5", None)],
)
def test_parse_amount(text, expected):
    assert parsing.parse_amount(text) == expected


# -------------------------------------------------------------- warranty ---

@pytest.mark.parametrize(
    "text, expected",
    [("CPU AMD RYZEN5 7500F 3-Y *P25", 36), ("ATX CASE 5F BLACK 1-Y", 12),
     ("SSD LEXAR NM790 5 YEARS", 60), ("ประกัน 2 ปี", 24), ("warranty 6 months", 6),
     ("DDR5 16x1 L-T", None), ("MOUSE M-250", None), (None, None)],
)
def test_parse_months(text, expected):
    assert parsing.parse_months(text) == expected


# -------------------------------------------------------- baseline (arm A) ---

JIB_STYLE = """\
JIB
ใบเสร็จรับเงิน
เลขที่ : IS00186-6908-000775 วันที่ : 23/08/2026 11:50
1004000021   4,590   1   4,590.00
CPU AMD AM5 RYZEN5 7500F 3-Y
1007000228   4,000   1   4,000.00
M/B MSI B650M GAMING PLUS WIFI 3-Y
3099000299   0.00   1   0.00
MOUSE ARROW-X M-250 [ PROMOTION ]
ราคารวม   8,590.00
(VAT Included)
Tel 061-823-7252
"""

ONE_LINE_STYLE = """\
Power Buy
Date 01/03/2025
Dell Latitude 5540 32,900.00
Laptop sleeve 890.00
Subtotal 33,790.00
Total 33,790.00
"""


def test_baseline_two_line_layout():
    got = parsing.extract_baseline(JIB_STYLE)
    assert got["vendor_name"] == "JIB"
    assert got["purchase_date"] == "2026-08-23"
    assert got["total_amount"] == "8590.00"
    prices = [i["price"] for i in got["line_items"]]
    assert prices == ["4590.00", "4000.00", "0.00"]
    assert got["line_items"][0]["name"].startswith("CPU AMD")
    assert got["line_items"][0]["warranty_months"] == 36
    # A SKU must never be offered as a serial number.
    assert all(i["serial_number"] is None for i in got["line_items"])


def test_baseline_one_line_layout_and_subtotal_ignored():
    got = parsing.extract_baseline(ONE_LINE_STYLE)
    assert got["vendor_name"] == "Power Buy"
    assert got["purchase_date"] == "2025-03-01"
    assert got["total_amount"] == "33790.00"
    assert [i["price"] for i in got["line_items"]] == ["32900.00", "890.00"]


def test_baseline_prefers_the_labelled_date_over_one_in_the_address():
    text = "JIB\nจ.ปทุมธานี 01/11/2017 12130\nวันที่ 23/08/2026\nTotal 10.00"
    assert parsing.extract_baseline(text)["purchase_date"] == "2026-08-23"


def test_baseline_survives_a_clipped_right_edge_and_table_borders():
    # Real Tesseract output for a photo whose right edge cut off the last "0".
    text = ("วันที่ : 23/08/2026 11:50\n"
            "| 1004000021      4590 1 4,590.0\n"
            "CPU AMD AMS RYZENS 7500F 3 *P25\n"
            "[1017000663      1490 1 1,490.0\n"
            "ATX CASE AEROCOOL 1-Y\n"
            "ราคารวม 6,080.0\n")
    got = parsing.extract_baseline(text)
    assert [i["price"] for i in got["line_items"]] == ["4590.00", "1490.00"]
    assert got["line_items"][1]["warranty_months"] == 12
    assert got["total_amount"] == "6080.00"


def test_baseline_on_empty_text_returns_empty_fields():
    got = parsing.extract_baseline("")
    assert got["vendor_name"] is None and got["purchase_date"] is None
    assert got["total_amount"] is None and got["line_items"] == []


# ------------------------------------------------------- model JSON (b, c) ---

def test_normalize_accepts_fenced_json_and_revalidates():
    raw = """```json
    {"vendor_name": " JIB ", "purchase_date": "23/08/2569", "total_amount": "37,570.00",
     "currency": "thb",
     "line_items": [{"name": "CPU", "price": "4590", "serial_number": "SN123",
                     "warranty_months": 36}]}
    ```"""
    got = parsing.normalize_llm_json(raw)
    assert got["vendor_name"] == "JIB"
    assert got["purchase_date"] == "2026-08-23"     # BE converted even if the model did not
    assert got["total_amount"] == "37570.00"
    assert got["currency"] == "THB"
    assert got["line_items"][0] == {
        "name": "CPU", "price": "4590.00", "serial_number": "SN123", "warranty_months": 36,
    }


def test_normalize_turns_bad_values_into_none():
    raw = ('{"purchase_date": "last Tuesday", "total_amount": "lots", "currency": "baht",'
           ' "line_items": [{"name": "X", "price": null, "warranty_months": 9999}, "junk"]}')
    got = parsing.normalize_llm_json(raw)
    assert got["purchase_date"] is None and got["total_amount"] is None
    assert got["currency"] is None
    assert got["line_items"] == [
        {"name": "X", "price": None, "serial_number": None, "warranty_months": None}
    ]


def test_normalize_rejects_output_without_json():
    with pytest.raises(ValueError):
        parsing.normalize_llm_json("Sorry, I cannot read this receipt.")


# --------------------------------------------------------------- scoring ---

TRUTH = {
    "vendor_name": "JIB",
    "purchase_date": "2026-08-23",
    "total_amount": "8590.00",
    "line_items": [
        {"name": "CPU AMD AM5 RYZEN5 7500F 3-Y", "price": "4590.00", "warranty_months": 36},
        {"name": "M/B MSI B650M GAMING PLUS WIFI 3-Y", "price": "4000.00", "warranty_months": 36},
    ],
}


def test_score_perfect_reading():
    pred = {**TRUTH, "vendor_name": "J.I.B. Computer", "line_items": TRUTH["line_items"]}
    got = scoring.score_receipt(pred, TRUTH)
    assert (got["vendor"], got["date"], got["total"]) == ("correct", "correct", "correct")
    assert got["items_matched"] == 2 and got["warranty_correct"] == 2


def test_vendor_may_have_several_acceptable_names():
    truth = {**TRUTH, "vendor_name": ["JIB", "เจ.ไอ.บี."]}
    thai = scoring.score_receipt({"vendor_name": "บริษัท เจ.ไอ.บี. คอมพิวเตอร์ จำกัด"}, truth)
    other = scoring.score_receipt({"vendor_name": "Power Buy"}, truth)
    assert thai["vendor"] == "correct" and other["vendor"] == "wrong"


def test_wrong_and_empty_are_reported_apart():
    pred = {"vendor_name": None, "purchase_date": "2017-11-01", "total_amount": "8590",
            "line_items": []}
    got = scoring.score_receipt(pred, TRUTH)
    assert got["vendor"] == "empty"
    assert got["date"] == "wrong"          # the dangerous outcome
    assert got["total"] == "correct"       # "8590" and "8590.00" are the same amount
    assert got["items_matched"] == 0


def test_item_needs_the_right_price_and_a_roughly_alike_name():
    pred = {"line_items": [
        {"name": "CPU AMD RYZEN5 7500F", "price": "4590.00", "warranty_months": 12},
        {"name": "M/B MSI B650M", "price": "9999.00", "warranty_months": 36},  # wrong price
    ]}
    got = scoring.score_receipt(pred, TRUTH)
    assert got["items_matched"] == 1
    assert got["warranty_expected"] == 2 and got["warranty_correct"] == 0  # 12 != 36


def test_fields_missing_from_ground_truth_are_not_scored():
    got = scoring.score_receipt({"purchase_date": "2026-01-01"}, {"vendor_name": "JIB"})
    assert got["date"] == "n/a" and got["total"] == "n/a"
    assert got["items_truth"] is None


def test_summary_table_has_one_row_per_arm():
    row = {"arm": "a", "file": "x.jpg", "seconds": 1.0, "error": None,
           "score": scoring.score_receipt({**TRUTH}, TRUTH)}
    table = scoring.summarize([row], {"a": "Tesseract + regex"})
    assert "Tesseract + regex" in table and "1 / 0 / 0" in table
