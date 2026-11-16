import Button from "@/components/Button";
import Card from "@/components/Card";
import type { AssetCondition, OcrDocument } from "@/types/documents";

import { type AssetDraft, draftFromScan, isReceiptComplete, warrantyEndLabel } from "./draft";
import Field, { inputClasses } from "./Field";

interface ReceiptReviewProps {
  drafts: AssetDraft[];
  /** Original OCR line-item index for each draft; null for a user-added card. */
  ocrLineItemIndexes: Array<number | null>;
  onChange: (index: number, changes: Partial<AssetDraft>) => void;
  scan: OcrDocument | null;
  error: { index: number; message: string } | null;
  canAddAsset: boolean;
  onAddAsset: () => void;
  onRemoveAsset: (index: number) => void;
  onBack: () => void;
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

/** Review all assets found on one receipt before confirming the document. */
export default function ReceiptReview({
  drafts,
  ocrLineItemIndexes,
  onChange,
  scan,
  error,
  canAddAsset,
  onAddAsset,
  onRemoveAsset,
  onBack,
  onConfirm,
  onCancel,
}: ReceiptReviewProps) {
  const allComplete = drafts.length > 0 && drafts.every(isReceiptComplete);

  return (
    <div className="flex flex-col gap-3 md:gap-4">
      <div className="flex flex-col gap-[3px]">
        <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground md:text-[17px] md:tracking-[-0.34px]">
          {scan?.status === "extracted" ? "Review assets from this receipt" : "Enter receipt details"}
        </h2>
        <p className="text-[11px] tracking-[-0.22px] text-muted-light md:text-[12px]">
          Review each product. Receipt details are pre-filled and can be edited for each asset.
        </p>
      </div>

      {drafts.map((draft, index) => {
        const lineItemIndex = ocrLineItemIndexes[index];
        const ocr = scan?.status === "extracted" && lineItemIndex !== null && lineItemIndex !== undefined
          ? draftFromScan(scan, lineItemIndex)
          : null;
        const fromOcr = (key: keyof AssetDraft) => Boolean(ocr?.[key]);
        const ocrCount = ocr
          ? ["name", "vendor_name", "purchase_date", "price", "invoice_number", "category_name", "warranty_duration_months"]
              .filter((key) => fromOcr(key as keyof AssetDraft)).length
          : 0;
        const item = lineItemIndex === null || lineItemIndex === undefined
          ? null
          : scan?.extracted?.line_items[lineItemIndex] ?? null;
        const webSource = item?.warranty_source ?? null;
        const webSourceUrl = webSource?.url && /^https:\/\//.test(webSource.url) ? webSource.url : null;
        const durationFromWeb = Boolean(webSourceUrl) && ocr?.warranty_duration_months === draft.warranty_duration_months;
        const chosen = draft.warranty_duration_months;
        const durations = chosen && !DURATIONS.some((duration) => duration.value === chosen)
          ? [...DURATIONS, { value: chosen, label: `${chosen} months` }].sort((a, b) => Number(a.value) - Number(b.value))
          : DURATIONS;
        const endLabel = warrantyEndLabel(draft);
        const fieldId = (name: string) => `${name}-${index}`;

        return (
          <div key={`asset-${index}`} className="flex flex-col gap-3 md:flex-row md:items-start md:gap-5">
            <Card className="flex flex-col gap-3 p-4 md:flex-1 md:gap-4 md:px-6 md:py-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-[3px]">
                  <h3 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">
                    Asset {index + 1}
                  </h3>
                  <p className="text-[11px] tracking-[-0.22px] text-muted-light">
                    Fields marked * are required. Everything stays editable.
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {ocr && (
                    <span className="rounded-full bg-status-active-soft px-2.5 py-[5px] text-[10px] font-semibold text-status-active">
                      OCR · {ocrCount} fields
                    </span>
                  )}
                  {drafts.length > 1 && canAddAsset && (
                    <button
                      type="button"
                      onClick={() => onRemoveAsset(index)}
                      aria-label={`Remove asset ${index + 1}`}
                      className="rounded-lg px-2 py-1 text-[12px] font-semibold text-status-expired hover:bg-status-expired-soft"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>

              {error?.index === index && (
                <p role="alert" className="rounded-lg bg-status-expired-soft px-3 py-2 text-[12px] font-medium text-status-expired">
                  {error.message} Please correct this asset and try again.
                </p>
              )}

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-x-4 md:gap-y-3.5">
                <Field id={fieldId("vendor")} label="Vendor" required fromOcr={fromOcr("vendor_name")}>
                  <input id={fieldId("vendor")} className={inputClasses} value={draft.vendor_name}
                    onChange={(event) => onChange(index, { vendor_name: event.target.value })} />
                </Field>
                <Field id={fieldId("purchase-date")} label="Purchase Date" required fromOcr={fromOcr("purchase_date")}>
                  <input id={fieldId("purchase-date")} type="date" className={inputClasses} value={draft.purchase_date}
                    onChange={(event) => onChange(index, { purchase_date: event.target.value })} />
                </Field>
                <Field id={fieldId("product-name")} label="Product Name" required fromOcr={fromOcr("name")} wide>
                  <input id={fieldId("product-name")} className={inputClasses} value={draft.name}
                    onChange={(event) => onChange(index, { name: event.target.value })} />
                </Field>
                <Field id={fieldId("invoice-number")} label="Invoice Number" required fromOcr={fromOcr("invoice_number")}>
                  <input id={fieldId("invoice-number")} className={inputClasses} value={draft.invoice_number}
                    onChange={(event) => onChange(index, { invoice_number: event.target.value })} />
                </Field>
                <Field id={fieldId("price")} label={`Price (${draft.currency})`} required fromOcr={fromOcr("price")}>
                  <input id={fieldId("price")} inputMode="decimal" className={inputClasses} value={draft.price}
                    onChange={(event) => onChange(index, { price: event.target.value })} />
                </Field>
                <Field id={fieldId("category")} label="Category" required fromOcr={fromOcr("category_name")}>
                  <input id={fieldId("category")} className={inputClasses} placeholder="e.g. Laptop" value={draft.category_name}
                    onChange={(event) => onChange(index, { category_name: event.target.value })} />
                </Field>
                <Field id={fieldId("condition")} label="Condition">
                  <select id={fieldId("condition")} className={inputClasses} value={draft.condition}
                    onChange={(event) => onChange(index, { condition: event.target.value as AssetCondition | "" })}>
                    <option value="">Choose a condition</option>
                    {CONDITIONS.map((condition) => <option key={condition.value} value={condition.value}>{condition.label}</option>)}
                  </select>
                </Field>
              </div>
            </Card>

            <Card className="flex flex-col gap-3 p-4 md:w-[380px] md:shrink-0 md:gap-4 md:px-[22px] md:py-5">
              <div className="flex flex-col gap-[3px]">
                <h3 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">Warranty Details</h3>
                <p className="text-[11px] tracking-[-0.22px] text-muted-light">Required. The expiry date is worked out for you.</p>
              </div>

              <Field id={fieldId("warranty-provider")} label="Warranty Provider" required>
                <input id={fieldId("warranty-provider")} className={inputClasses} placeholder="e.g. Apple Limited Warranty"
                  value={draft.warranty_provider} onChange={(event) => onChange(index, { warranty_provider: event.target.value })} />
              </Field>
              <Field id={fieldId("warranty-start")} label="Start Date" required>
                <input id={fieldId("warranty-start")} type="date" className={inputClasses} value={draft.warranty_start_date}
                  onChange={(event) => onChange(index, { warranty_start_date: event.target.value })} />
              </Field>
              <Field id={fieldId("warranty-duration")} label="Duration" required fromOcr={fromOcr("warranty_duration_months")}>
                <select id={fieldId("warranty-duration")} className={inputClasses} value={draft.warranty_duration_months}
                  onChange={(event) => onChange(index, { warranty_duration_months: event.target.value })}>
                  <option value="">Choose a duration</option>
                  {durations.map((duration) => <option key={duration.value} value={duration.value}>{duration.label}</option>)}
                </select>
                {durationFromWeb && webSourceUrl && (
                  <p className="text-[12px] tracking-[-0.24px] text-muted">
                    Not printed on the receipt. Found online, so please check it:{" "}
                    <a href={webSourceUrl} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand underline">
                      {new URL(webSourceUrl).hostname}
                    </a>
                    {webSource?.evidence ? ` — “${webSource.evidence}”` : ""}
                  </p>
                )}
              </Field>
              <div className="flex flex-col gap-[7px]">
                <p className="text-[12px] font-semibold tracking-[-0.24px] text-muted">Expiry Date (auto-calculated)</p>
                <p className="flex h-12 items-center rounded-[9px] bg-canvas px-3.5 text-[14px] font-medium tracking-[-0.28px] text-muted md:h-[46px]">
                  {endLabel ?? "Choose a start date and duration"}
                </p>
              </div>
            </Card>
          </div>
        );
      })}

      {canAddAsset && (
        <button type="button" onClick={onAddAsset}
          className="flex h-12 items-center justify-center rounded-[10px] border border-dashed border-brand bg-brand-subtle text-[14px] font-semibold text-brand hover:bg-brand-subtle/70">
          + Add another asset
        </button>
      )}

      <div className="flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-between">
        <div className="md:w-40"><Button variant="secondary" onClick={onBack}>Back</Button></div>
        <div className="flex flex-col-reverse gap-3 md:flex-row">
          <div className="md:w-40"><Button variant="secondary" onClick={onCancel}>Cancel</Button></div>
          <div className="md:w-60"><Button disabled={!allComplete} onClick={onConfirm}>Continue to serial numbers</Button></div>
        </div>
      </div>
    </div>
  );
}
