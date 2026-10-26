import type { ReactNode } from "react";

/** Shared look for every box: M07 field style (3382:636). */
export const inputClasses =
  "h-12 w-full rounded-[9px] border border-border bg-surface px-3.5 text-[14px] font-medium tracking-[-0.28px] text-foreground outline-none focus:border-brand md:h-[46px]";

interface FieldProps {
  id: string;
  label: string;
  required?: boolean;
  /** Green "OCR": this value was read from the receipt. */
  fromOcr?: boolean;
  /** Amber "Low confidence": OCR read it, but it is easy to misread; check it (3569:454). */
  lowConfidence?: boolean;
  /** Spans both columns of the desktop grid. */
  wide?: boolean;
  children: ReactNode;
}

/** A label (with optional "*" and a badge) above one input. Used by every Add Asset step. */
export default function Field({ id, label, required, fromOcr, lowConfidence, wide, children }: FieldProps) {
  return (
    <div className={`flex flex-col gap-[7px] ${wide ? "md:col-span-2" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-[12px] font-semibold tracking-[-0.24px] text-foreground">
          {label}
          {required && " *"}
        </label>
        {lowConfidence ? (
          <span className="rounded-full bg-status-expiring-soft px-[9px] py-1 text-[10px] font-semibold tracking-[-0.2px] text-status-expiring">
            Low confidence
          </span>
        ) : (
          fromOcr && (
            <span className="rounded-full bg-status-active-soft px-[9px] py-1 text-[10px] font-semibold tracking-[-0.2px] text-status-active">
              OCR
            </span>
          )
        )}
      </div>
      {children}
    </div>
  );
}
