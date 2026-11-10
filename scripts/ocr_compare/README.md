# OCR comparison: Tesseract vs Claude on Bedrock

A throwaway harness for deciding how WarrantyTrack reads receipts. It runs three
approaches over the same receipt photos and scores each against answers you
write by hand.

| Arm | What it does | Needs AWS |
|---|---|---|
| **A** Tesseract + regex | Tesseract OCR, then a deliberately simple regex parser | no |
| **B** Claude vision | Sends the image straight to Claude through Bedrock | yes |
| **C** Tesseract text → Claude | Tesseract OCR, then Claude reads only the text | yes |

How to read the comparison:

- **A vs C** — same OCR text, different parser. Shows what a language model is worth over regex.
- **C vs B** — same model, different input. Shows what you lose by letting Tesseract read the image first.

## Setup

```bash
brew install tesseract tesseract-lang        # tha + eng language data
cd scripts/ocr_compare
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                           # parsing and scoring tests, no AWS needed
```

For arms B and C you also need AWS credentials (`aws configure` or SSO) and a
Bedrock model ID. **Copy the model ID from the Bedrock console** (Model catalog,
or the inference profile ID if your region requires one). Do not guess it, and
check the model is enabled for your account and region.

```bash
export AWS_REGION=ap-southeast-1
export BEDROCK_MODEL_ID="<paste from the console>"
```

## Prepare the data

1. Put 10–15 receipt photos in `receipts/` (`.jpg`, `.png`, `.webp`). Mix them on purpose:
   Thai only, Thai + English, English only, skewed or dark photos, faded thermal paper,
   a long receipt, a receipt with a Buddhist Era date.
2. Write `ground_truth.json` by hand, one entry per file name. See
   `ground_truth.example.json`. Any field you leave out is not scored.
   `vendor_name` may be a list when the shop prints both a Thai and an English name.
   Dates are `YYYY-MM-DD` in the Gregorian calendar.

`receipts/`, `out/` and `ground_truth.json` are gitignored. Real receipts contain
names, phone numbers and card digits, so do not commit them.

## Decide before you run

Write down your pass/fail bar first, otherwise it is easy to rationalise afterwards.
Suggestions to adapt:

- Date and total: `wrong` count as close to 0 as possible. A wrong prefilled value is
  worse than an empty one, because the user accepts it without looking.
- Item recall and warranty accuracy: the higher the better, but a lower `wrong` count wins ties.
- Cost and latency per receipt: acceptable for a student project budget?

## Run

```bash
python run.py --arms a              # Tesseract only
python run.py --limit 1             # one receipt on every arm: check that AWS works first
python run.py                       # everything
python run.py --price-in 3 --price-out 15   # USD per 1M tokens, from the Bedrock pricing page
```

Output goes to `out/`:

- `summary.md` — the comparison table (`c/w/e` = correct / wrong / empty)
- `results.json` — one row per receipt per arm
- `raw/` — per-receipt extraction, score, the model's raw reply, and the Tesseract text

Open `raw/` for any receipt that scored badly. The Tesseract text next to the model
reply usually shows right away whether the OCR or the parser was at fault.

## Caveats

- Arm A is a simple baseline, not the best regex parser possible. A tuned parser would
  close some of the gap, though not the Thai-text and layout problems.
- Tesseract needs the `tha` language data. The harness stops with a clear message if it is missing.
- Item matching needs the right price and a roughly similar name, so a garbled name with the
  correct price still counts as matched.
- Tokens and cost are only recorded for B and C. Cost is an estimate from the prices you pass in.
- Receipts are sent to AWS Bedrock in arms B and C. Use receipts you are happy to share with
  the AWS account that owns the Bedrock access (for example a course account).
- With 10–15 receipts, differences of one or two fields are noise. Look for large gaps.
