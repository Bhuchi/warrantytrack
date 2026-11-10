import Button from "@/components/Button";
import Card from "@/components/Card";
import type { AssetCondition, OcrDocument } from "@/types/documents";

import { type AssetDraft, draftFromScan, isReceiptComplete, warrantyEndLabel } from "./draft";
import Field, { inputClasses } from "./Field";

interface ReceiptReviewProps {
  draft: AssetDraft;
  /** Change some fields and keep the rest. */
  onChange: (changes: Partial<AssetDraft>) => void;
  /** What OCR read, to mark those fields "OCR"; null for manual entry. */
  scan: OcrDocument | null;
  onConfirm: () => void;
  onCancel: () => void;
}

const CONDITIONS: { value: AssetCondition; label: string }[] = [
  { value: "new", label: "New" },
  { value: "good", label: "Good" },
  { value: "fair", label: "Fair" },
  { value: "damaged", label: "Damaged" },
];

const DURATIONS = [
  { value: "6", label: "6 months" },
  { value: "12", label: "1 year" },
  { value: "24", label: "2 years" },
  { value: "36", label: "3 years" },
];

/**
 * Step 1's review: check and correct what OCR read, or type it all in for
 * manual entry. Mobile 3569:361, desktop 3570:451.
 *
 * Required fields follow issue #34: everything except Condition, including
 * Category, Invoice Number and the whole warranty.
 *
 * Category is typed, like Vendor: POST /assets adds a new name to the list.
 * TODO: Department and Location (desktop frame) need lists from the backend
 * (/departments) that do not exist yet.
 */
export default function ReceiptReview({ draft, onChange, scan, onConfirm, onCancel }: ReceiptReviewProps) {
  // What OCR filled in, to decide where the "OCR" badges go.
  const ocr = scan?.status === "extracted" ? draftFromScan(scan) : null;
  const fromOcr = (key: keyof AssetDraft) => Boolean(ocr?.[key]);
  const ocrCount = ocr ? ["name", "vendor_name", "purchase_date", "price"].filter((key) => fromOcr(key as keyof AssetDraft)).length : 0;
  const endLabel = warrantyEndLabel(draft);

  return (
    <div className="flex flex-col gap-3 md:gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:gap-5">
        <Card className="flex flex-col gap-3 p-4 md:flex-1 md:gap-4 md:px-6 md:py-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-[3px]">
              <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground md:text-[17px] md:tracking-[-0.34px]">
                {ocr ? "Review extracted information" : "Enter receipt details"}
              </h2>
              <p className="text-[11px] tracking-[-0.22px] text-muted-light md:text-[12px]">
                Fields marked * are required. Everything stays editable.
              </p>
            </div>
            {ocr && (
              <span className="hidden shrink-0 rounded-full bg-status-active-soft px-2.5 py-[5px] text-[11px] font-semibold text-status-active md:inline">
                OCR complete · {ocrCount} fields
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-x-4 md:gap-y-3.5">
            <Field id="vendor" label="Vendor" required fromOcr={fromOcr("vendor_name")}>
              <input
                id="vendor"
                className={inputClasses}
                value={draft.vendor_name}
                onChange={(event) => onChange({ vendor_name: event.target.value })}
              />
            </Field>
            <Field id="purchase-date" label="Purchase Date" required fromOcr={fromOcr("purchase_date")}>
              <input
                id="purchase-date"
                type="date"
                className={inputClasses}
                value={draft.purchase_date}
                onChange={(event) => onChange({ purchase_date: event.target.value })}
              />
            </Field>
            <Field id="product-name" label="Product Name" required fromOcr={fromOcr("name")} wide>
              <input
                id="product-name"
                className={inputClasses}
                value={draft.name}
                onChange={(event) => onChange({ name: event.target.value })}
              />
            </Field>
            <Field id="invoice-number" label="Invoice Number" required>
              <input
                id="invoice-number"
                className={inputClasses}
                value={draft.invoice_number}
                onChange={(event) => onChange({ invoice_number: event.target.value })}
              />
            </Field>
            <Field id="price" label={`Price (${draft.currency})`} required fromOcr={fromOcr("price")}>
              <input
                id="price"
                inputMode="decimal"
                className={inputClasses}
                value={draft.price}
                onChange={(event) => onChange({ price: event.target.value })}
              />
            </Field>
            <Field id="category" label="Category" required>
              <input
                id="category"
                className={inputClasses}
                placeholder="e.g. Laptop"
                value={draft.category_name}
                onChange={(event) => onChange({ category_name: event.target.value })}
              />
            </Field>
            <Field id="condition" label="Condition">
              <select
                id="condition"
                className={inputClasses}
                value={draft.condition}
                onChange={(event) => onChange({ condition: event.target.value as AssetCondition | "" })}
              >
                <option value="">Choose a condition</option>
                {CONDITIONS.map((condition) => (
                  <option key={condition.value} value={condition.value}>
                    {condition.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Card>

        <Card className="flex flex-col gap-3 p-4 md:w-[380px] md:shrink-0 md:gap-4 md:px-[22px] md:py-5">
          <div className="flex flex-col gap-[3px]">
            <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground md:text-[17px] md:tracking-[-0.34px]">
              Warranty Details
            </h2>
            <p className="text-[11px] tracking-[-0.22px] text-muted-light md:text-[12px]">
              Required. The expiry date is worked out for you.
            </p>
          </div>

          <Field id="warranty-provider" label="Warranty Provider" required>
            <input
              id="warranty-provider"
              className={inputClasses}
              placeholder="e.g. Apple Limited Warranty"
              value={draft.warranty_provider}
              onChange={(event) => onChange({ warranty_provider: event.target.value })}
            />
          </Field>
          <Field id="warranty-start" label="Start Date" required>
            <input
              id="warranty-start"
              type="date"
              className={inputClasses}
              value={draft.warranty_start_date}
              onChange={(event) => onChange({ warranty_start_date: event.target.value })}
            />
          </Field>
          <Field id="warranty-duration" label="Duration" required>
            <select
              id="warranty-duration"
              className={inputClasses}
              value={draft.warranty_duration_months}
              onChange={(event) => onChange({ warranty_duration_months: event.target.value })}
            >
              <option value="">Choose a duration</option>
              {DURATIONS.map((duration) => (
                <option key={duration.value} value={duration.value}>
                  {duration.label}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex flex-col gap-[7px]">
            <p className="text-[12px] font-semibold tracking-[-0.24px] text-muted">Expiry Date (auto-calculated)</p>
            <p className="flex h-12 items-center rounded-[9px] bg-canvas px-3.5 text-[14px] font-medium tracking-[-0.28px] text-muted md:h-[46px]">
              {endLabel ?? "Choose a start date and duration"}
            </p>
          </div>
        </Card>
      </div>

      <div className="flex flex-col gap-3 md:flex-row-reverse md:justify-start">
        <div className="md:w-60">
          <Button disabled={!isReceiptComplete(draft)} onClick={onConfirm}>
            Confirm
          </Button>
        </div>
        <div className="md:w-40">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
