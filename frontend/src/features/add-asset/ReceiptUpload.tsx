import Image from "next/image";

import { ScanIcon } from "@/components/NavIcons";

/** What is happening to the chosen file. */
export type UploadStatus = "idle" | "scanning" | "done" | "failed";

interface ReceiptUploadProps {
  /** "photo" opens the camera on phones; "upload" opens the file picker. */
  method: "upload" | "photo";
  file: File | null;
  status: UploadStatus;
  /** Shown in red when status is "failed". */
  error: string | null;
  /** Called with the file the user picked or dropped. */
  onFile: (file: File) => void;
}

/** "1.2 MB" or "640 KB". */
function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/**
 * The drop zone and, once a file is chosen, its status card. Mobile M06
 * (3569:187), OCR failed (3569:274), desktop D06 (3570:18).
 */
export default function ReceiptUpload({ method, file, status, error, onFile }: ReceiptUploadProps) {
  const isPhoto = method === "photo";
  const failed = status === "failed";

  return (
    <>
      {/* Desktop: a file can also be dropped onto the zone. */}
      <div
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const dropped = event.dataTransfer.files[0];
          if (dropped) onFile(dropped);
        }}
        className="flex flex-col items-center gap-2.5 rounded-[14px] border-[1.5px] border-dashed border-brand bg-brand-subtle px-4 py-[26px] text-center"
      >
        <div className="flex size-[52px] items-center justify-center rounded-full bg-surface">
          <Image src="/icons/upload-cloud.svg" alt="" width={24} height={24} />
        </div>
        <p className="text-[15px] font-bold tracking-[-0.3px] text-brand">
          {isPhoto ? (
            "Take a photo of the receipt"
          ) : (
            <>
              <span className="md:hidden">Choose a file to upload</span>
              <span className="hidden md:inline">Drag &amp; drop your file here</span>
            </>
          )}
        </p>
        <p className="text-[12px] tracking-[-0.24px] text-muted">
          {isPhoto ? "Make sure the whole receipt is in frame" : "PDF, JPG or PNG · max 10 MB"}
        </p>

        {/* The real input is hidden; the label below is what people tap. */}
        <input
          id="receipt-file"
          type="file"
          accept={isPhoto ? "image/*" : "application/pdf,image/jpeg,image/png"}
          capture={isPhoto ? "environment" : undefined}
          className="sr-only"
          onChange={(event) => {
            const picked = event.target.files?.[0];
            if (picked) onFile(picked);
            // Lets the same file be picked again after a failure.
            event.target.value = "";
          }}
        />
        <label
          htmlFor="receipt-file"
          className="flex h-[42px] cursor-pointer items-center rounded-lg bg-brand px-[22px] text-[14px] font-bold tracking-[-0.28px] text-brand-foreground"
        >
          {isPhoto ? "Take Photo" : "Browse Files"}
        </label>
      </div>

      {file && (
        <div
          className={`flex flex-col gap-2.5 rounded-xl border bg-surface px-3.5 pt-[13px] pb-3.5 ${
            failed ? "border-status-expired" : "border-border"
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-[9px] bg-brand-subtle">
              <Image src="/icons/file-doc.svg" alt="" width={17} height={17} />
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
              <p className="truncate text-[13px] font-semibold tracking-[-0.26px] text-foreground">{file.name}</p>
              <p className="text-[11px] tracking-[-0.22px] text-muted-light">{formatSize(file.size)}</p>
            </div>
            <p
              className={`shrink-0 text-[13px] font-bold ${
                failed ? "text-status-expired" : status === "done" ? "text-status-active" : "text-brand"
              }`}
            >
              {failed ? "Failed" : status === "done" ? "Done" : "Reading…"}
            </p>
          </div>

          {/* While reading, the bar pulses: the mock has no real percentage to show. */}
          <div className="h-[7px] overflow-hidden rounded-full bg-track">
            <div
              className={`h-full rounded-full ${
                failed
                  ? "w-full bg-status-expired"
                  : status === "done"
                    ? "w-full bg-brand"
                    : "w-2/3 animate-pulse bg-brand"
              }`}
            />
          </div>

          <p
            className={`flex items-center gap-2 text-[11px] tracking-[-0.22px] ${
              failed ? "text-status-expired" : "text-muted"
            }`}
          >
            <ScanIcon className="size-3.5 shrink-0" />
            {failed
              ? `${error ?? "We couldn't read this receipt."} Enter the details yourself.`
              : status === "done"
                ? "Receipt read. Check the details on the next screen."
                : "AWS Textract is extracting your data…"}
          </p>
        </div>
      )}
    </>
  );
}
