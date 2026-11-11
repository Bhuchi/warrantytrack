"""Warranty lookup on the web. Pure: the search and the model are stubbed."""

from __future__ import annotations

import pytest

from app.services import warranty_lookup as wl

RESULTS = [
    {"title": "HyperX SoloCast | JIB", "url": "https://www.jib.co.th/p/solocast", "content": "ประกัน 2 ปี"},
    {"title": "Other", "url": "https://example.com/x", "content": "..."},
]


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(wl.settings, "warranty_search_provider", "tavily")
    monkeypatch.setattr(wl.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(wl.settings, "bedrock_model_id", "test-model")


def test_off_by_default_makes_no_calls(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not search when disabled")

    monkeypatch.setattr(wl, "_search", boom)
    data = {"vendor_name": "JIB", "line_items": [{"name": "HyperX SoloCast", "warranty_months": None}]}
    assert wl.fill_missing_warranties(data) == data
    assert "warranty_source" not in data["line_items"][0]


@pytest.mark.parametrize(
    ("vendor", "domain"),
    [
        ("JIB Computer Group", "jib.co.th"),
        ("บริษัท เจ.ไอ.บี. คอมพิวเตอร์ กรุ๊ป จำกัด", "jib.co.th"),
        ("Power Buy", "powerbuy.co.th"),
        ("Some Corner Shop", None),
        (None, None),
    ],
)
def test_vendor_domain_hint(vendor, domain):
    assert wl._vendor_domain(vendor) == domain


def test_valid_answer_is_accepted():
    f = wl._validate(
        {"warranty_months": 24, "source_url": "https://www.jib.co.th/p/solocast", "evidence": "  ประกัน   2 ปี "},
        RESULTS,
    )
    assert f == wl.WarrantyFinding(24, "https://www.jib.co.th/p/solocast", "ประกัน 2 ปี")


@pytest.mark.parametrize(
    "answer",
    [
        {"warranty_months": 24, "source_url": "https://evil.example/pwn"},  # not a fetched result
        {"warranty_months": 24, "source_url": None},
        {"warranty_months": 999, "source_url": "https://example.com/x"},  # absurd
        {"warranty_months": "3 years", "source_url": "https://example.com/x"},
        {"warranty_months": None, "source_url": "https://example.com/x"},
        ["not", "an", "object"],
    ],
)
def test_untrustworthy_answers_become_none(answer):
    assert wl._validate(answer, RESULTS) is None


def test_shop_site_is_searched_first_then_the_open_web(on, monkeypatch):
    scopes = []

    def search(query, domain):
        scopes.append(domain)
        return RESULTS if domain is None else []

    monkeypatch.setattr(wl, "_search", search)
    monkeypatch.setattr(
        wl, "_ask_model",
        lambda p, v, r: wl.WarrantyFinding(24, r[0]["url"], None),
    )
    assert wl.lookup("JIB", "HyperX SoloCast").months == 24
    assert scopes == ["jib.co.th", None]


def test_fill_adds_months_and_source_but_never_overrides_the_receipt(on, monkeypatch):
    monkeypatch.setattr(wl, "lookup", lambda v, n: wl.WarrantyFinding(24, "https://www.jib.co.th/p/solocast", "ประกัน 2 ปี"))
    data = {
        "vendor_name": "JIB",
        "line_items": [
            {"name": "HyperX SoloCast", "warranty_months": None},
            {"name": "CPU Ryzen 5 7500F", "warranty_months": 36},
        ],
    }
    wl.fill_missing_warranties(data)
    assert data["line_items"][0]["warranty_months"] == 24
    assert data["line_items"][0]["warranty_source"]["url"] == "https://www.jib.co.th/p/solocast"
    assert data["line_items"][1]["warranty_months"] == 36
    assert "warranty_source" not in data["line_items"][1]


def test_a_failing_lookup_leaves_the_item_alone(on, monkeypatch):
    def fail(vendor, name):
        raise TimeoutError("search timed out")

    monkeypatch.setattr(wl, "lookup", fail)
    data = {"vendor_name": "JIB", "line_items": [{"name": "HyperX SoloCast", "warranty_months": None}]}
    wl.fill_missing_warranties(data)
    assert data["line_items"][0]["warranty_months"] is None


def test_lookups_per_receipt_are_capped(on, monkeypatch):
    calls = []
    monkeypatch.setattr(wl, "lookup", lambda v, n: calls.append(n))
    data = {"vendor_name": "JIB", "line_items": [{"name": f"Item {i}", "warranty_months": None} for i in range(10)]}
    wl.fill_missing_warranties(data)
    assert len(calls) == wl.MAX_LOOKUPS_PER_RECEIPT
