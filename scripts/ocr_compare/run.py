#!/usr/bin/env python3
"""Run the three OCR arms over a folder of receipts and score them.

    python run.py --arms a               # Tesseract only, no AWS needed
    python run.py --limit 1              # try one receipt on every arm first
    python run.py                        # everything

Bedrock arms need AWS credentials and BEDROCK_MODEL_ID (or --model-id).
Copy the model ID from the Bedrock console; do not guess it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import arms
import parsing
import scoring

HERE = Path(__file__).resolve().parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--receipts", type=Path, default=HERE / "receipts")
    p.add_argument("--truth", type=Path, default=HERE / "ground_truth.json")
    p.add_argument("--out", type=Path, default=HERE / "out")
    p.add_argument("--arms", default="a,b,c", help="comma list from: a, b, c")
    p.add_argument("--model-id", default=os.environ.get("BEDROCK_MODEL_ID"))
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-southeast-1"))
    p.add_argument("--lang", default="tha+eng", help="Tesseract languages")
    p.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode")
    p.add_argument("--max-side", type=int, default=2000, help="long-side cap for Bedrock images")
    # None = send no temperature. Some newer models reject the parameter
    # ("`temperature` is deprecated for this model").
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--price-in", type=float, help="USD per 1M input tokens, to estimate cost")
    p.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    p.add_argument("--limit", type=int, help="only the first N receipts")
    args = p.parse_args()

    chosen = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in chosen if a not in arms.ARM_NAMES]
    if unknown:
        p.error(f"unknown arm(s): {', '.join(unknown)}")
    needs_bedrock = any(a in chosen for a in ("b", "c"))
    if needs_bedrock and not args.model_id:
        p.error("arms b and c need --model-id or BEDROCK_MODEL_ID (copy it from the Bedrock console)")

    images = sorted(f for f in args.receipts.glob("*") if f.suffix.lower() in IMAGE_SUFFIXES)
    if args.limit:
        images = images[: args.limit]
    if not images:
        p.error(f"no receipt images in {args.receipts}")

    truth: dict[str, Any] = {}
    if args.truth.exists():
        truth = json.loads(args.truth.read_text(encoding="utf-8"))
    else:
        print(f"note: {args.truth.name} not found, results will not be scored", file=sys.stderr)

    client = arms.bedrock_client(args.region) if needs_bedrock else None
    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for image in images:
        print(f"\n{image.name}")
        ocr_text: str | None = None

        def record(arm: str, extracted: dict | None, **extra: Any) -> None:
            score = None
            if extracted is not None and image.name in truth:
                score = scoring.score_receipt(extracted, truth[image.name])
            rows.append({"arm": arm, "file": image.name, "score": score, **extra})
            (raw_dir / f"{image.stem}.{arm}.json").write_text(
                json.dumps(
                    {"extracted": extracted, "score": score, **extra},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            status = "error: " + extra["error"] if extra.get("error") else "ok"
            print(f"  [{arm}] {arms.ARM_NAMES[arm]:<26} {status}")

        if "a" in chosen or "c" in chosen:
            started = time.perf_counter()
            try:
                ocr_text = arms.tesseract_text(str(image), args.lang, args.psm)
                (raw_dir / f"{image.stem}.tesseract.txt").write_text(ocr_text, encoding="utf-8")
                ocr_seconds = time.perf_counter() - started
            except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                ocr_seconds, ocr_error = time.perf_counter() - started, str(exc)
                for arm in ("a", "c"):
                    if arm in chosen:
                        record(arm, None, seconds=ocr_seconds, error=f"tesseract: {ocr_error}")
                ocr_text = None

        if "a" in chosen and ocr_text is not None:
            record("a", parsing.extract_baseline(ocr_text), seconds=ocr_seconds, error=None)

        if "b" in chosen:
            try:
                result = arms.bedrock_vision(
                    client, args.model_id, str(image), args.max_side, args.temperature
                )
                record(
                    "b",
                    parsing.normalize_llm_json(result["raw"]),
                    seconds=result["seconds"],
                    tokens_in=result["tokens_in"],
                    tokens_out=result["tokens_out"],
                    model_output=result["raw"],
                    error=None,
                )
            except Exception as exc:  # noqa: BLE001
                record("b", None, seconds=0, error=f"{type(exc).__name__}: {exc}")

        if "c" in chosen and ocr_text is not None:
            try:
                result = arms.bedrock_text(client, args.model_id, ocr_text, args.temperature)
                record(
                    "c",
                    parsing.normalize_llm_json(result["raw"]),
                    seconds=ocr_seconds + result["seconds"],
                    tokens_in=result["tokens_in"],
                    tokens_out=result["tokens_out"],
                    model_output=result["raw"],
                    error=None,
                )
            except Exception as exc:  # noqa: BLE001
                record("c", None, seconds=ocr_seconds, error=f"{type(exc).__name__}: {exc}")

    names = {a: arms.ARM_NAMES[a] for a in chosen}
    summary = scoring.summarize(rows, names, args.price_in, args.price_out)
    (args.out / "summary.md").write_text(summary + "\n", encoding="utf-8")
    (args.out / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n" + summary)
    print(f"\nPer-receipt detail: {raw_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
