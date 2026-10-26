"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/Button";
import Modal from "@/components/Modal";
import { CameraIcon, PencilIcon, UploadIcon } from "@/components/NavIcons";
import type { OcrDocument } from "@/types/documents";

import { type AssetDraft, EMPTY_DRAFT, draftFromScan } from "./draft";
import MethodCards, { type MethodOption } from "./MethodCards";
import ReceiptReview from "./ReceiptReview";
import ReceiptUpload, { type UploadStatus } from "./ReceiptUpload";
import SerialStep from "./SerialStep";
import StepProgress from "./StepProgress";
import { scanReceipt } from "./scanReceipt";

/** How the user brings the receipt in. Manual entry is always offered up front. */
type ReceiptMethod = "upload" | "photo" | "manual";

/** Where the user is inside step 1. */
type ReceiptPhase = "choose" | "scanning" | "scanned" | "failed" | "review";

/** Matches the "max 10 MB" in the drop zone. */
const MAX_FILE_BYTES = 10 * 1024 * 1024;

/** Step 1's method cards. Mobile shows the short label; desktop adds the description (D06). */
const RECEIPT_METHODS: readonly MethodOption<ReceiptMethod>[] = [
  { id: "upload", label: "Upload", desktopLabel: "Upload File", description: "Invoice or receipt (PDF, JPG, PNG)", Icon: UploadIcon },
  { id: "photo", label: "Photo", desktopLabel: "Take Photo", description: "Capture a receipt with your camera", Icon: CameraIcon },
  { id: "manual", label: "Manual", desktopLabel: "Manual Entry", description: "Type the asset details yourself", Icon: PencilIcon },
];

/**
 * Add Asset, the 3-step flow: receipt (required), serial number (required),
 * box photo (optional). Figma mobile 3569:187, desktop 3570:18.
 *
 * Runs in the browser ("use client") because it reacts to taps and typing.
 * The wizard owns all the answers (`draft`); each step reads it and reports
 * changes back. Nothing is saved until the last step.
 */
export default function AddAssetWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [method, setMethod] = useState<ReceiptMethod>("upload");
  const [phase, setPhase] = useState<ReceiptPhase>("choose");
  const [file, setFile] = useState<File | null>(null);
  const [scan, setScan] = useState<OcrDocument | null>(null);
  const [draft, setDraft] = useState<AssetDraft>(EMPTY_DRAFT);
  const [discardOpen, setDiscardOpen] = useState(false);

  /** Change some fields of the draft and keep the rest. */
  function updateDraft(changes: Partial<AssetDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
  }

  /** Picking another method starts the receipt over. */
  function chooseMethod(next: ReceiptMethod) {
    setMethod(next);
    setPhase("choose");
    setFile(null);
    setScan(null);
    setDraft(EMPTY_DRAFT);
  }

  /** Manual entry, chosen up front or offered after a failed scan: start from an empty form. */
  function enterManually() {
    setDraft(EMPTY_DRAFT);
    setPhase("review");
  }

  /** Runs when a file is picked or dropped: show "Reading…", wait for OCR, then show the result. */
  async function handleFile(picked: File) {
    setFile(picked);

    if (picked.size > MAX_FILE_BYTES) {
      setScan({ id: "", status: "failed", extracted: null, error: "This file is larger than 10 MB." });
      setPhase("failed");
      return;
    }

    setPhase("scanning");
    const result = await scanReceipt(picked);
    setScan(result);

    if (result.status === "extracted") {
      setDraft(draftFromScan(result));
      setPhase("scanned");
    } else {
      // OCR failed: offer manual entry automatically (Figma 3569:274).
      setMethod("manual");
      setPhase("failed");
    }
  }

  const uploadStatus: UploadStatus =
    phase === "scanning" ? "scanning" : phase === "scanned" ? "done" : phase === "failed" ? "failed" : "idle";

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

      <StepProgress step={step} />

      {step === 2 && (
        <SerialStep
          draft={draft}
          onChange={updateDraft}
          ocrSerial={scan?.extracted?.line_items[0]?.serial_number ?? null}
          onBack={() => setStep(1)}
          onCancel={() => setDiscardOpen(true)}
          onConfirm={() => setStep(3)}
        />
      )}

      {step === 3 && (
        // TODO: step 3, box / storage photo (FE-11, CLOUDAPPG5-129).
        <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-[13px] text-muted">
          Box photo step comes next (FE-11).
        </p>
      )}

      {step === 1 && phase === "review" && (
        <ReceiptReview
          draft={draft}
          onChange={updateDraft}
          scan={scan}
          onConfirm={() => setStep(2)}
          onCancel={() => setDiscardOpen(true)}
        />
      )}

      {step === 1 && phase !== "review" && (
        <>
          <MethodCards options={RECEIPT_METHODS} value={method} onSelect={chooseMethod} />

          {/* Shown for Upload and Photo, and kept on screen after a failure so the red card explains why. */}
          {(method !== "manual" || phase === "failed") && (
            <ReceiptUpload
              method={method === "photo" ? "photo" : "upload"}
              file={file}
              status={uploadStatus}
              error={scan?.error ?? null}
              onFile={handleFile}
            />
          )}

          {phase === "failed" || method === "manual" ? (
            <Button onClick={enterManually}>Enter details manually</Button>
          ) : (
            <Button disabled={phase !== "scanned"} onClick={() => setPhase("review")}>
              Continue to review
            </Button>
          )}
        </>
      )}

      <Modal
        open={discardOpen}
        onClose={() => setDiscardOpen(false)}
        title="Discard this asset?"
        actions={
          <>
            <Button variant="secondary" onClick={() => setDiscardOpen(false)}>
              Keep editing
            </Button>
            <Button onClick={() => router.push("/dashboard")}>Discard</Button>
          </>
        }
      >
        Your changes will be lost. This can&apos;t be undone.
      </Modal>
    </div>
  );
}
