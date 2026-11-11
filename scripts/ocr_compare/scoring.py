"""Score extracted fields against hand-written ground truth, and summarise.

Pure functions, no AWS or Tesseract, unit-tested in test_ocr_compare.py.

Every field gets one of three outcomes, and the difference matters:

  correct   the value matches the truth
  wrong     a value was given and it is wrong   <- the dangerous one
  empty     no value was given                  <- the user types it

The project rule is that a wrong value is worse than an empty one, because the
user accepts a prefilled value without looking. So `wrong` is reported on its
own rather than folded into an accuracy percentage.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from parsing import parse_amount

_NAME_MATCH_THRESHOLD = 0.4


def _norm(text: str | None) -> str:
    return re.sub(r"\W+", "", (text or "").lower())


def _status(pred: Any, truth: Any) -> str:
    if truth is None:
        return "n/a"  # the ground truth does not cover this field
    if pred in (None, ""):
        return "empty"
    return "correct" if pred == truth else "wrong"


def _vendor_status(pred: str | None, truth: str | list[str] | None) -> str:
    """`truth` may be a list of acceptable names: a shop often prints a Thai
    name and an English name, and either is a right answer."""
    if truth is None:
        return "n/a"
    p = _norm(pred)
    if not p:
        return "empty"
    for name in [truth] if isinstance(truth, str) else truth:
        t = _norm(name)
        if t and (p == t or (min(len(p), len(t)) >= 3 and (p in t or t in p))):
            return "correct"
    return "wrong"


def _match_items(pred: list[dict], truth: list[dict]) -> list[tuple[dict, dict]]:
    """Pair each true line item with at most one predicted item.

    Same price is required; the name only has to look roughly alike, because
    OCR garbles names but a price is either right or it is not.
    """
    used: set[int] = set()
    pairs: list[tuple[dict, dict]] = []
    for expected in truth:
        want = parse_amount(expected.get("price"))
        best, best_score = None, _NAME_MATCH_THRESHOLD
        for idx, got in enumerate(pred):
            if idx in used or want is None or parse_amount(got.get("price")) != want:
                continue
            score = SequenceMatcher(
                None, _norm(got.get("name")), _norm(expected.get("name"))
            ).ratio()
            if score >= best_score:
                best, best_score = idx, score
        if best is not None:
            used.add(best)
            pairs.append((pred[best], expected))
    return pairs


def score_receipt(pred: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    pred_items = pred.get("line_items") or []
    truth_items = truth.get("line_items")
    result: dict[str, Any] = {
        "vendor": _vendor_status(pred.get("vendor_name"), truth.get("vendor_name")),
        "date": _status(pred.get("purchase_date"), truth.get("purchase_date")),
        "total": _status(
            parse_amount(pred.get("total_amount")), parse_amount(truth.get("total_amount"))
        ),
        "items_pred": len(pred_items),
        "items_truth": None,
        "items_matched": None,
        "warranty_expected": None,
        "warranty_correct": None,
    }
    if truth_items is not None:
        pairs = _match_items(pred_items, truth_items)
        result["items_truth"] = len(truth_items)
        result["items_matched"] = len(pairs)
        expected_warranty = [(g, t) for g, t in pairs if t.get("warranty_months") is not None]
        result["warranty_expected"] = sum(
            1 for t in truth_items if t.get("warranty_months") is not None
        )
        result["warranty_correct"] = sum(
            1 for g, t in expected_warranty if g.get("warranty_months") == t["warranty_months"]
        )
    return result


def _triplet(rows: list[dict], key: str) -> str:
    counts = {"correct": 0, "wrong": 0, "empty": 0}
    for row in rows:
        status = row["score"][key] if row.get("score") else None
        if status in counts:
            counts[status] += 1
    return f"{counts['correct']} / {counts['wrong']} / {counts['empty']}"


def _ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.0%}" if denominator else "-"


def summarize(
    rows: list[dict[str, Any]],
    arm_names: dict[str, str],
    price_in: float | None = None,
    price_out: float | None = None,
) -> str:
    """A Markdown table, one row per arm.

    `rows` items: {arm, file, score|None, seconds, tokens_in, tokens_out, error}
    """
    header = (
        "| Arm | Receipts | Date c/w/e | Total c/w/e | Vendor c/w/e | Item recall | "
        "Item precision | Warranty | Errors | Avg sec | Tokens in/out | Est. cost USD |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for arm, name in arm_names.items():
        mine = [r for r in rows if r["arm"] == arm]
        if not mine:
            continue
        scored = [r for r in mine if r.get("score")]
        matched = sum(r["score"]["items_matched"] or 0 for r in scored)
        truth_n = sum(r["score"]["items_truth"] or 0 for r in scored)
        pred_n = sum(r["score"]["items_pred"] for r in scored if r["score"]["items_truth"] is not None)
        w_ok = sum(r["score"]["warranty_correct"] or 0 for r in scored)
        w_all = sum(r["score"]["warranty_expected"] or 0 for r in scored)
        tok_in = sum(r.get("tokens_in") or 0 for r in mine)
        tok_out = sum(r.get("tokens_out") or 0 for r in mine)
        cost = (
            f"{(tok_in * price_in + tok_out * price_out) / 1e6:.4f}"
            if price_in is not None and price_out is not None and (tok_in or tok_out)
            else "-"
        )
        lines.append(
            f"| {name} | {len(mine)} | {_triplet(scored, 'date')} | "
            f"{_triplet(scored, 'total')} | {_triplet(scored, 'vendor')} | "
            f"{_ratio(matched, truth_n)} | {_ratio(matched, pred_n)} | {_ratio(w_ok, w_all)} | "
            f"{sum(1 for r in mine if r.get('error'))} | "
            f"{sum(r.get('seconds') or 0 for r in mine) / len(mine):.1f} | "
            f"{tok_in or '-'} / {tok_out or '-'} | {cost} |"
        )
    lines.append(
        "\n`c/w/e` = correct / wrong / empty. `wrong` means a value was given and it was "
        "incorrect, which is worse than `empty`."
    )
    return "\n".join(lines)
