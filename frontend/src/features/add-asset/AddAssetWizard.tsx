"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/Button";
import Modal from "@/components/Modal";
import { CameraIcon, PencilIcon, UploadIcon } from "@/components/NavIcons";
import { useToast } from "@/components/ToastProvider";
import { PhotoUploadError } from "@/features/assets/assetPhoto";
import { ApiError } from "@/lib/api";
import type { OcrDocument } from "@/types/documents";

import BoxPhotoStep from "./BoxPhotoStep";
import { additionalDraftFrom, type AssetDraft, draftFromScan, EMPTY_DRAFT } from "./draft";
import MethodCards, { type MethodOption } from "./MethodCards";
import ReceiptReview from "./ReceiptReview";
import ReceiptUpload, { type UploadStatus } from "./ReceiptUpload";
import { NOT_A_RECEIPT_FILE_MESSAGE, isReceiptFile } from "./receiptFile";
import SerialStep from "./SerialStep";
import StepProgress from "./StepProgress";
import { saveAssets } from "./saveAsset";
import { queueSavedToast } from "./savedToast";
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

function confirmError(error: unknown): { index: number; message: string } | null {
  if (!(error instanceof ApiError) || error.status !== 422 || typeof error.body !== "object" || error.body === null) {
    return null;
  }
  const detail = (error.body as { detail?: unknown }).detail;
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const first = detail[0] as { loc?: unknown; msg?: unknown };
  if (!Array.isArray(first.loc) || typeof first.msg !== "string") return null;
  const index = first.loc[2];
  return typeof index === "number" ? { index, message: first.msg } : null;
}

/** Add Asset: review every receipt line item, then complete per-asset details before one save. */
export default function AddAssetWizard() {
  const router = useRouter();
  const showToast = useToast();
  const [step, setStep] = useState(1);
  const [method, setMethod] = useState<ReceiptMethod>("upload");
  const [phase, setPhase] = useState<ReceiptPhase>("choose");
  const [file, setFile] = useState<File | null>(null);
  const [scan, setScan] = useState<OcrDocument | null>(null);
  const [drafts, setDrafts] = useState<AssetDraft[]>([EMPTY_DRAFT]);
  /** Original OCR line-item index for each draft; null means added by the user. */
  const [ocrLineItemIndexes, setOcrLineItemIndexes] = useState<Array<number | null>>([null]);
  const [activeAssetIndex, setActiveAssetIndex] = useState(0);
  const [saveError, setSaveError] = useState<{ index: number; message: string } | null>(null);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  function updateDraft(index: number, changes: Partial<AssetDraft>) {
    setSaveError(null);
    setDrafts((current) => current.map((draft, draftIndex) =>
      draftIndex === index ? { ...draft, ...changes } : draft,
    ));
  }

  function resetDrafts(nextDrafts: AssetDraft[], nextOcrIndexes: Array<number | null>) {
    setDrafts(nextDrafts);
    setOcrLineItemIndexes(nextOcrIndexes);
    setActiveAssetIndex(0);
  }

  /** Picking another method starts the receipt over. */
  function chooseMethod(next: ReceiptMethod) {
    setMethod(next);
    setPhase("choose");
    setFile(null);
    setScan(null);
    resetDrafts([EMPTY_DRAFT], [null]);
  }

  function addAsset() {
    const source = drafts[drafts.length - 1] ?? EMPTY_DRAFT;
    setDrafts((current) => [...current, additionalDraftFrom(source)]);
    setOcrLineItemIndexes((current) => [...current, null]);
    setSaveError(null);
  }

  function removeAsset(index: number) {
    setDrafts((current) => current.filter((_, draftIndex) => draftIndex !== index));
    setOcrLineItemIndexes((current) => current.filter((_, draftIndex) => draftIndex !== index));
    setSaveError(null);
  }

  /** Save all receipt assets through the document confirm endpoint in one request. */
  async function saveAll(finalDrafts: AssetDraft[] = drafts) {
    setSaving(true);
    try {
      const created = await saveAssets(finalDrafts);
      const names = finalDrafts.map((draft) => draft.name.trim()).filter(Boolean);
      const title = created.ids.length === 1 ? "Asset saved successfully" : "Assets saved successfully";
      const message = created.ids.length === 1
        ? `${names[0] ?? "The asset"} was added.`
        : `${created.ids.length} assets were added.`;
      queueSavedToast(title, message);
      showToast({ tone: "success", title, message });
      router.push("/dashboard");
    } catch (error) {
      if (error instanceof PhotoUploadError) {
        showToast({ tone: "error", title: "Could not save the assets", message: error.message });
        setSaving(false);
        return;
      }
      const issue = confirmError(error);
      if (issue) {
        setSaveError(issue);
        setActiveAssetIndex(0);
        setStep(1);
        setPhase("review");
        setSaving(false);
        return;
      }
      showToast({ tone: "error", title: "Could not save the assets", message: "Please check the entries and try again." });
      setSaving(false);
    }
  }

  function confirmSerialStep() {
    if (activeAssetIndex < drafts.length - 1) {
      setActiveAssetIndex((current) => current + 1);
      return;
    }
    setActiveAssetIndex(0);
    setStep(3);
  }

  function backFromSerialStep() {
    if (activeAssetIndex > 0) {
      setActiveAssetIndex((current) => current - 1);
      return;
    }
    setStep(1);
  }

  function finishBoxPhotoStep(clearCurrent = false) {
    const nextDrafts = clearCurrent
      ? drafts.map((draft, index) => index === activeAssetIndex
        ? { ...draft, location: "", location_photo: null }
        : draft)
      : drafts;
    if (clearCurrent) setDrafts(nextDrafts);

    if (activeAssetIndex < drafts.length - 1) {
      setActiveAssetIndex((current) => current + 1);
      return;
    }
    void saveAll(nextDrafts);
  }

  /** Manual entry, chosen up front or offered after a failed scan. */
  function enterManually() {
    resetDrafts([EMPTY_DRAFT], [null]);
    setPhase("review");
  }

  /** Read the receipt and create one draft for each detected line item. */
  async function handleFile(picked: File) {
    setFile(picked);
    // Starting another upload discards any earlier OCR drafts.
    setScan(null);
    resetDrafts([EMPTY_DRAFT], [null]);

    if (!isReceiptFile(picked)) {
      setScan({ id: "", status: "failed", extracted: null, error: NOT_A_RECEIPT_FILE_MESSAGE });
      setPhase("failed");
      return;
    }

    if (picked.size > MAX_FILE_BYTES) {
      setScan({ id: "", status: "failed", extracted: null, error: "This file is larger than 10 MB." });
      setPhase("failed");
      return;
    }

    setPhase("scanning");
    const result = await scanReceipt(picked);
    setScan(result);

    if (result.status === "extracted") {
      const itemCount = Math.max(1, result.extracted?.line_items.length ?? 0);
      const indexes = Array.from({ length: itemCount }, (_, index) => index < (result.extracted?.line_items.length ?? 0) ? index : null);
      resetDrafts(Array.from({ length: itemCount }, (_, index) => draftFromScan(result, index)), indexes);
      setPhase("scanned");
    } else {
      // OCR failed: offer manual entry automatically (Figma 3569:274).
      setMethod("manual");
      setPhase("failed");
    }
  }

  const uploadStatus: UploadStatus =
    phase === "scanning" ? "scanning" : phase === "scanned" ? "done" : phase === "failed" ? "failed" : "idle";
  const activeDraft = drafts[activeAssetIndex] ?? drafts[0] ?? EMPTY_DRAFT;

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

      {step > 1 && drafts.length > 1 && (
        <p className="text-center text-[13px] font-semibold text-muted" aria-live="polite">
          Asset {activeAssetIndex + 1} of {drafts.length}
        </p>
      )}

      {step === 2 && (
        <SerialStep
          key={activeAssetIndex}
          draft={activeDraft}
          onChange={(changes) => updateDraft(activeAssetIndex, changes)}
          ocrSerial={ocrLineItemIndexes[activeAssetIndex] === null
            ? null
            : scan?.extracted?.line_items[ocrLineItemIndexes[activeAssetIndex] ?? 0]?.serial_number ?? null}
          onBack={backFromSerialStep}
          onCancel={() => setDiscardOpen(true)}
          onConfirm={confirmSerialStep}
        />
      )}

      {step === 3 && (
        <BoxPhotoStep
          key={activeAssetIndex}
          draft={activeDraft}
          onChange={(changes) => updateDraft(activeAssetIndex, changes)}
          assetNumber={activeAssetIndex + 1}
          assetCount={drafts.length}
          saving={saving}
          onBack={() => {
            if (activeAssetIndex > 0) setActiveAssetIndex((current) => current - 1);
            else {
              setActiveAssetIndex(drafts.length - 1);
              setStep(2);
            }
          }}
          onSave={() => finishBoxPhotoStep()}
          onSkip={() => finishBoxPhotoStep(true)}
        />
      )}

      {step === 1 && phase === "review" && (
        <ReceiptReview
          drafts={drafts}
          ocrLineItemIndexes={ocrLineItemIndexes}
          onChange={updateDraft}
          scan={scan}
          error={saveError}
          canAddAsset={scan?.status === "extracted"}
          onAddAsset={addAsset}
          onRemoveAsset={removeAsset}
          onBack={() => {
            if (scan?.status === "extracted") setPhase("scanned");
            else if (scan) setPhase("failed");
            else setPhase("choose");
          }}
          onConfirm={() => { setActiveAssetIndex(0); setStep(2); }}
          onCancel={() => setDiscardOpen(true)}
        />
      )}

      {step === 1 && phase !== "review" && (
        <>
          <MethodCards options={RECEIPT_METHODS} value={method} onSelect={chooseMethod} />

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
        title="Discard these assets?"
        actions={
          <>
            <Button variant="secondary" onClick={() => setDiscardOpen(false)}>Keep editing</Button>
            <Button onClick={() => router.push("/dashboard")}>Discard</Button>
          </>
        }
      >
        Your changes will be lost. This can&apos;t be undone.
      </Modal>
    </div>
  );
}
