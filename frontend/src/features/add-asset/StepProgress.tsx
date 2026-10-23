import Image from "next/image";
import { Fragment } from "react";

/** Short names for the mobile card, longer ones for the desktop stepper (D06 3570:539). */
const STEPS = [
  { short: "Receipt", long: "Receipt" },
  { short: "Serial number", long: "Serial number (required)" },
  { short: "Box photo (optional)", long: "Box photo (optional)" },
];

interface StepProgressProps {
  /** The current step, 1 to 3. */
  step: number;
}

/**
 * Where the user is in Add Asset. Mobile: a card with a bar (M06 3569:187).
 * Desktop: three numbered circles joined by lines (D06 3570:539).
 */
export default function StepProgress({ step }: StepProgressProps) {
  const percent = Math.round((step / STEPS.length) * 100);

  return (
    <>
      {/* Mobile */}
      <div className="flex flex-col gap-2.5 rounded-xl border border-border bg-surface px-4 py-3.5 md:hidden">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[13px] font-semibold tracking-[-0.26px] text-brand">
            Step {step} of {STEPS.length} · {STEPS[step - 1].short}
          </p>
          <p className="text-[12px] font-bold text-muted-light">{percent}%</p>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-track">
          <div className="h-full rounded-full bg-brand" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {/* Desktop */}
      <ol className="hidden items-center gap-2 rounded-[14px] border border-border bg-surface px-6 py-4 md:flex">
        {STEPS.map((item, index) => {
          const number = index + 1;
          const done = number < step;
          const current = number === step;

          return (
            <Fragment key={item.long}>
              {/* The line before each step after the first: blue once the step before it is done. */}
              {index > 0 && <li aria-hidden="true" className={`h-0.5 min-w-4 flex-1 ${done || current ? "bg-brand" : "bg-border"}`} />}
              <li aria-current={current ? "step" : undefined} className="flex shrink-0 items-center gap-3">
                <span
                  className={`flex size-8 items-center justify-center rounded-full text-[13px] font-bold ${
                    done || current ? "bg-brand text-brand-foreground" : "border border-border bg-canvas text-muted-light"
                  }`}
                >
                  {done ? <Image src="/icons/check.svg" alt="" width={16} height={16} /> : number}
                </span>
                <span
                  className={`text-[13px] tracking-[-0.26px] ${
                    current ? "font-bold text-brand" : done ? "font-medium text-foreground" : "font-medium text-muted-light"
                  }`}
                >
                  {item.long}
                  {done && <span className="sr-only"> (done)</span>}
                </span>
              </li>
            </Fragment>
          );
        })}
      </ol>
    </>
  );
}
