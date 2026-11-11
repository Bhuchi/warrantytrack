"""A model's JSON reply -> the `extracted` shape. Pure: no AWS, no network."""

from __future__ import annotations

import pytest

from app.services.ocr import OcrError, _json_from_reply, parse_model_json


def test_clean_answer_is_normalised():
    out = parse_model_json({
        "vendor_name": " JIB ",
        "purchase_date": "2568-03-12",
        "total_amount": "฿32,900.00",
        "currency": "thb",
        "line_items": [{"name": "Laptop", "serial_number": "ABC123", "price": "32900", "warranty_months": 36}],
    })
    assert out["vendor_name"] == "JIB"
    assert out["total_amount"] == "32900.00"
    assert out["currency"] == "THB"
    # warranty_months is not part of the API shape (docs/api.md), so it is dropped.
    assert out["line_items"] == [{"name": "Laptop", "serial_number": "ABC123", "price": "32900.00"}]


def test_bad_values_become_none_not_garbage():
    out = parse_model_json({"purchase_date": "yesterday", "total_amount": "abc", "line_items": [{}, "x"]})
    assert out["purchase_date"] is None
    assert out["total_amount"] is None
    assert out["line_items"] == []


def test_non_object_is_an_error():
    with pytest.raises(OcrError):
        parse_model_json([])  # type: ignore[arg-type]


def test_json_fence_is_stripped():
    assert _json_from_reply('```json\n{"vendor_name": "A"}\n```') == {"vendor_name": "A"}
    assert _json_from_reply('{"vendor_name": "A"}') == {"vendor_name": "A"}


def test_prose_is_an_error():
    with pytest.raises(OcrError):
        _json_from_reply("Sorry, I cannot read this.")
