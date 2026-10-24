import { useRef, useState } from "react";

import Button from "@/components/Button";
import Card from "@/components/Card";
import { CameraIcon, PencilIcon, ScanIcon } from "@/components/NavIcons";

import type { AssetDraft } from "./draft";
import Field, { inputClasses } from "./Field";
import MethodCards, { type MethodOption } from "./MethodCards";
import { scanSerial } from "./scanSerial";

type SerialMethod = "scan" | "type";

const SERIAL_METHODS: readonly MethodOption<SerialMethod>[] = [
  { id: "scan", label: "Scan", desktopLabel: "Scan serial", description: "Point your camera at the sticker on the device.", Icon: CameraIcon },
  { id: "type", label: "Type", desktopLabel: "Type it", description: "Enter the serial number yourself.", Icon: PencilIcon },
];

interface SerialStepProps {
  draft: AssetDraft;
  onChange: (changes: Partial<AssetDraft>) => void;
  /** The serial the receipt OCR read, if any, so it can be flagged. */
  ocrSerial: string | null;
  onBack: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * Step 2, the serial number. Required: there is no Skip (team decision,
 * 18 Oct). Mobile 3569:454, desktop 3571:18.
 *
 * Scan opens the camera straight away and fills the box; Type puts the cursor
 * in the box. Any serial OCR read is flagged "Low confidence" until the user
 * changes it, because 0/O and 1/I are easy to misread.
 */
export default function SerialStep({ draft, onChange, ocrSerial, onBack, onCancel, onConfirm }: SerialStepProps) {
  const [method, setMethod] = useState<SerialMethod>("scan");
  const [scanning, setScanning] = useState(false);
  const [scannedSerial, setScannedSerial] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const serialInput = useRef<HTMLInputElement>(null);

  const serial = draft.serial_number;
  const lowConfidence = serial !== "" && (serial === ocrSerial || serial === scannedSerial);

  function selectMethod(next: SerialMethod) {
    setMethod(next);
    // Scan: open the camera now. Type: jump to the box.
    if (next === "scan") photoInput.current?.click();
    else serialInput.current?.focus();
  }

  async function handlePhoto(photo: File) {
    setScanning(true);
    setScanError(null);
    const result = await scanSerial(photo);
    setScanning(false);

    if (result.serial) {
      setScannedSerial(result.serial);
      onChange({ serial_number: result.serial });
    } else {
      // Nothing readable: switch to typing it in.
      setScanError(result.error);
      setMethod("type");
      serialInput.current?.focus();
    }
  }

  return (
    <div className="flex flex-col gap-3 md:gap-4">
      <MethodCards options={SERIAL_METHODS} value={method} onSelect={selectMethod} />

      <input
        ref={photoInput}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        aria-label="Photo of the serial number sticker"
        onChange={(event) => {
          const picked = event.target.files?.[0];
          if (picked) handlePhoto(picked);
          event.target.value = "";
        }}
      />

      <Card className="flex flex-col gap-3 p-4 md:gap-4 md:px-6 md:py-5">
        <div className="flex flex-col gap-[3px]">
          <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground md:text-[17px] md:tracking-[-0.34px]">
            Serial number
          </h2>
          <p className="text-[11px] tracking-[-0.22px] text-muted-light md:text-[12px]">
            Required. You need it when you make a warranty claim.
          </p>
        </div>

        <Field id="serial-number" label="Serial Number" required lowConfidence={lowConfidence}>
          <input
            id="serial-number"
            ref={serialInput}
            className={inputClasses}
            autoComplete="off"
            spellCheck={false}
            value={serial}
            onChange={(event) => onChange({ serial_number: event.target.value })}
          />
        </Field>

        {(scanning || scanError) && (
          <p
            className={`flex items-center gap-2 text-[12px] tracking-[-0.24px] ${scanError ? "text-status-expired" : "text-muted"}`}
          >
            <ScanIcon className="size-3.5 shrink-0" />
            {scanError ?? "Reading the serial number…"}
          </p>
        )}

        <p className="text-[12px] tracking-[-0.24px] text-muted">
          Usually on a sticker on the back or bottom of the device. Needed when you make a warranty claim.
        </p>
      </Card>

      {/* Mobile: Confirm on top, then Cancel, then Back. Desktop: Back on the left, Cancel and Confirm on the right. */}
      <div className="flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-between">
        <div className="md:w-40">
          <Button variant="secondary" onClick={onBack}>
            Back
          </Button>
        </div>
        <div className="flex flex-col-reverse gap-3 md:flex-row">
          <div className="md:w-40">
            <Button variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
          </div>
          <div className="md:w-60">
            <Button disabled={serial.trim() === "" || scanning} onClick={onConfirm}>
              Confirm
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
