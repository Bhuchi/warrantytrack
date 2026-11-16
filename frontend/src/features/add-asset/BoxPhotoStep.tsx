import Image from "next/image";
import { useEffect, useMemo } from "react";

import Button from "@/components/Button";
import Card from "@/components/Card";

import type { AssetDraft } from "./draft";
import Field, { inputClasses } from "./Field";

interface BoxPhotoStepProps {
  draft: AssetDraft;
  onChange: (changes: Partial<AssetDraft>) => void;
  assetNumber: number;
  assetCount: number;
  /** True while the asset is being saved: buttons are disabled. */
  saving: boolean;
  onBack: () => void;
  /** Saves with the photo and note. */
  onSave: () => void;
  /** Saves without them. */
  onSkip: () => void;
}

/**
 * Step 3, the box / storage photo. Optional: Save and "Skip for now" both save
 * the asset. Mobile 3569:568, desktop 3571:331. No Cancel here: Skip already
 * finishes the flow, and Back leads to Cancel on the earlier steps.
 */
export default function BoxPhotoStep({ draft, onChange, assetNumber, assetCount, saving, onBack, onSave, onSkip }: BoxPhotoStepProps) {
  const photo = draft.location_photo;

  // A temporary address for the picked photo so it can be shown before upload.
  const previewUrl = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  // Free it when the photo changes or the step closes.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  return (
    <div className="flex flex-col gap-3 md:gap-4">
      <div className="flex flex-col items-center gap-2.5 rounded-[14px] border-[1.5px] border-dashed border-brand bg-brand-subtle px-4 py-[26px] text-center">
        {previewUrl ? (
          <Image
            src={previewUrl}
            alt="Photo of the box or where it is kept"
            width={160}
            height={120}
            unoptimized
            className="h-[120px] w-40 rounded-lg object-cover"
          />
        ) : (
          <div className="flex size-[52px] items-center justify-center rounded-full bg-surface">
            <Image src="/icons/upload-cloud.svg" alt="" width={24} height={24} />
          </div>
        )}
        <p className="text-[15px] font-bold tracking-[-0.3px] text-brand">
          {photo ? photo.name : "Add a photo of the box"}
        </p>
        <p className="text-[12px] tracking-[-0.24px] text-muted">Or of where it&apos;s kept · JPG, PNG or HEIC</p>

        <input
          id="box-photo"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          capture="environment"
          className="sr-only"
          onChange={(event) => {
            const picked = event.target.files?.[0];
            if (picked) onChange({ location_photo: picked });
            event.target.value = "";
          }}
        />
        <div className="flex items-center gap-3">
          <label
            htmlFor="box-photo"
            className="flex h-[42px] cursor-pointer items-center rounded-lg bg-brand px-[22px] text-[14px] font-bold tracking-[-0.28px] text-brand-foreground"
          >
            {photo ? "Retake Photo" : "Take Photo"}
          </label>
          {photo && (
            <button
              type="button"
              onClick={() => onChange({ location_photo: null })}
              className="h-[42px] px-2 text-[14px] font-semibold tracking-[-0.28px] text-brand"
            >
              Remove
            </button>
          )}
        </div>
      </div>

      <Card className="flex flex-col gap-3 p-4 md:px-6 md:py-5">
        <Field id="box-note" label="Note">
          <textarea
            id="box-note"
            rows={3}
            placeholder="e.g. Box is on the top shelf in the storage room"
            className={`${inputClasses} h-24 resize-none py-3 md:h-24`}
            value={draft.location}
            onChange={(event) => onChange({ location: event.target.value })}
          />
        </Field>
        <p className="text-[12px] tracking-[-0.24px] text-muted">
          Optional. Shown on the asset&apos;s page for warranties that need the original box.
        </p>
      </Card>

      {/* Mobile: Save, Skip, Back stacked. Desktop: Back on the left, Skip and Save on the right. */}
      <div className="flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-between">
        <div className="md:w-40">
          <Button variant="secondary" disabled={saving} onClick={onBack}>
            Back
          </Button>
        </div>
        <div className="flex flex-col-reverse gap-3 md:flex-row">
          <div className="md:w-44">
            <Button variant="secondary" disabled={saving} onClick={onSkip}>
              {assetNumber < assetCount ? "Skip this asset" : "Skip and save"}
            </Button>
          </div>
          <div className="md:w-60">
            <Button disabled={saving} onClick={onSave}>
              {saving ? "Saving…" : assetNumber < assetCount ? "Continue" : assetCount > 1 ? "Save assets" : "Save asset"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
