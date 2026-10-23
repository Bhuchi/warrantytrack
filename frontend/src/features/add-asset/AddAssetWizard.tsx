"use client";

import { useState } from "react";

import { CameraIcon, PencilIcon, UploadIcon } from "@/components/NavIcons";

/** How the user brings the receipt in. Manual entry is always offered up front. */
type ReceiptMethod = "upload" | "photo" | "manual";

/** The three method cards. Mobile shows the short label; desktop adds the description (D06). */
const METHODS = [
  { id: "upload", label: "Upload", desktopLabel: "Upload File", description: "Invoice or receipt (PDF, JPG, PNG)", Icon: UploadIcon },
  { id: "photo", label: "Photo", desktopLabel: "Take Photo", description: "Capture a receipt with your camera", Icon: CameraIcon },
  { id: "manual", label: "Manual", desktopLabel: "Manual Entry", description: "Type the asset details yourself", Icon: PencilIcon },
] as const;

/**
 * Add Asset, the 3-step flow: receipt (required), serial number (required),
 * box photo (optional). Figma mobile 3569:187, desktop 3570:18.
 *
 * Runs in the browser ("use client") because it reacts to taps and typing.
 * Built up one piece at a time: so far the header, progress and method cards.
 *
 * TODO: desktop shows a 3-step stepper instead of the progress card (3396:7449).
 */
export default function AddAssetWizard() {
  const [method, setMethod] = useState<ReceiptMethod>("upload");

  return (
    <div className="flex flex-col gap-3 md:gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand md:text-[30px] md:tracking-[-0.6px]">
          Add Asset
        </h1>
        <p className="text-[12px] tracking-[-0.24px] text-muted md:text-[15px] md:tracking-[-0.3px]">
          Scan the receipt, or enter the details yourself.
        </p>
      </div>

      <div className="flex flex-col gap-2.5 rounded-xl border border-border bg-surface px-4 py-3.5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[13px] font-semibold tracking-[-0.26px] text-brand">Step 1 of 3 · Receipt</p>
          <p className="text-[12px] font-bold text-muted-light">33%</p>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-track">
          <div className="h-full w-1/3 rounded-full bg-brand" />
        </div>
      </div>

      <div className="flex gap-2.5 md:gap-4">
        {METHODS.map(({ id, label, desktopLabel, description, Icon }) => {
          const selected = method === id;

          return (
            <button
              key={id}
              type="button"
              aria-pressed={selected}
              onClick={() => setMethod(id)}
              className={`flex flex-1 flex-col items-center gap-2 rounded-xl py-3.5 md:items-start md:gap-2.5 md:px-[18px] md:py-4 ${
                selected ? "border-2 border-brand bg-brand-subtle" : "border border-border bg-surface"
              }`}
            >
              <span
                className={`flex size-[38px] items-center justify-center rounded-[10px] md:size-10 ${
                  selected ? "bg-brand text-brand-foreground" : "bg-canvas text-muted"
                }`}
              >
                <Icon className="size-[19px] md:size-5" />
              </span>
              <span className={`text-[13px] font-bold tracking-[-0.26px] md:text-[15px] ${selected ? "text-brand" : "text-foreground"}`}>
                <span className="md:hidden">{label}</span>
                <span className="hidden md:inline">{desktopLabel}</span>
              </span>
              <span className="hidden text-left text-[12px] tracking-[-0.24px] text-muted md:block">
                {description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
