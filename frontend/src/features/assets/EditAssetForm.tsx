"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import Button from "@/components/Button";
import Field, { inputClasses } from "@/features/add-asset/Field";
import type { AssetDetail, UpdateAssetRequest } from "@/types/assets";

import { getAsset } from "./getAsset";
import { updateAsset } from "./updateAsset";

/** Everything the form shows, as the strings the inputs hold. */
interface FormValues {
  name: string;
  serial_number: string;
  purchase_date: string;
  price: string;
  invoice_number: string;
  vendor_name: string;
  category_name: string;
  location_name: string;
  storage_note: string;
  warranty_provider: string;
  warranty_start_date: string;
  warranty_duration_months: string;
}

/**
 * Whole months from start to end, e.g. 2025-03-01 to 2027-03-01 is 24.
 * The detail response has the end date, but the form edits a duration, the
 * same as Add Asset, so it is worked out once here.
 */
function monthsBetween(start: string, end: string): number {
  const [startYear, startMonth] = start.split("-").map(Number);
  const [endYear, endMonth] = end.split("-").map(Number);
  return (endYear - startYear) * 12 + (endMonth - startMonth);
}

/** The asset as the form's starting values. Missing values become "". */
function toFormValues(asset: AssetDetail): FormValues {
  const warranty = asset.warranty;
  return {
    name: asset.name,
    serial_number: asset.serial_number,
    purchase_date: asset.purchase_date,
    price: asset.price ?? "",
    invoice_number: asset.invoice_number ?? "",
    vendor_name: asset.vendor?.name ?? "",
    category_name: asset.category?.name ?? "",
    location_name: asset.location?.name ?? "",
    storage_note: asset.storage_note ?? "",
    warranty_provider: warranty?.provider ?? "",
    warranty_start_date: warranty?.start_date ?? "",
    warranty_duration_months:
      warranty?.start_date ? String(monthsBetween(warranty.start_date, warranty.end_date)) : "",
  };
}

/**
 * Only what the user changed, in the PATCH shape. Anything left out stays as
 * it is on the backend, so an untouched form sends {} and changes nothing.
 */
function changedFields(before: FormValues, after: FormValues): UpdateAssetRequest {
  const changes: UpdateAssetRequest = {};
  const changed = (key: keyof FormValues) => before[key].trim() !== after[key].trim();

  if (changed("name")) changes.name = after.name.trim();
  if (changed("serial_number")) changes.serial_number = after.serial_number.trim();
  if (changed("purchase_date")) changes.purchase_date = after.purchase_date;
  if (Number(before.price) !== Number(after.price)) changes.price = after.price;
  if (changed("invoice_number")) changes.invoice_number = after.invoice_number.trim();
  if (changed("vendor_name")) changes.vendor_name = after.vendor_name.trim();
  if (changed("category_name")) changes.category_name = after.category_name.trim();

  // Optional fields: emptied means "clear it", which the API spells as null.
  if (changed("location_name")) {
    const location = after.location_name.trim();
    if (location) changes.location_name = location;
    else changes.location_id = null;
  }
  if (changed("storage_note")) changes.storage_note = after.storage_note.trim() || null;

  // The warranty is replaced as a whole, so any change sends all three parts.
  if (changed("warranty_provider") || changed("warranty_start_date") || changed("warranty_duration_months")) {
    changes.warranty = {
      provider: after.warranty_provider.trim(),
      start_date: after.warranty_start_date,
      duration_months: Number(after.warranty_duration_months),
    };
  }
  return changes;
}

/**
 * Edit Asset (/assets/{id}/edit). Bhuchi found the Edit button on Asset
 * Details did nothing; this is where it now goes.
 *
 * Same fields as the Add Asset review step, minus the receipt and photo,
 * which PATCH cannot change. Saving goes back to Asset Details.
 */
export default function EditAssetForm({ assetId }: { assetId: string }) {
  const router = useRouter();
  // undefined = loading, null = not found, otherwise the values as loaded.
  const [original, setOriginal] = useState<FormValues | null | undefined>(undefined);
  const [values, setValues] = useState<FormValues | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let ignore = false;
    getAsset(assetId)
      .then((asset) => {
        if (ignore) return;
        const loaded = asset && toFormValues(asset);
        setOriginal(loaded);
        setValues(loaded);
      })
      .catch(() => {
        if (!ignore) setLoadFailed(true);
      });
    return () => {
      ignore = true;
    };
  }, [assetId]);

  const detailHref = `/assets/${encodeURIComponent(assetId)}`;

  /** Updates one field; the rest stay as they are. */
  function set(key: keyof FormValues, value: string) {
    setValues((current) => current && { ...current, [key]: value });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!original || !values) return;

    const changes = changedFields(original, values);
    if (Object.keys(changes).length === 0) {
      router.push(detailHref);
      return;
    }

    setError(null);
    setSaving(true);
    try {
      await updateAsset(assetId, changes);
      router.push(detailHref);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Couldn't save your changes.");
      setSaving(false);
    }
  }

  /** A text-like input wired to one field. */
  const input = (key: keyof FormValues, props: Record<string, unknown> = {}) => (
    <input
      id={key}
      name={key}
      className={inputClasses}
      value={values?.[key] ?? ""}
      onChange={(event) => set(key, event.target.value)}
      {...props}
    />
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <Link
        href={detailHref}
        className="flex w-fit items-center gap-1.5 text-[13px] font-semibold tracking-[-0.26px] text-muted hover:text-brand"
      >
        <Image src="/icons/asset-back.svg" alt="" width={15} height={15} />
        Asset Details
      </Link>

      <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand md:text-[26px]">
        Edit Asset
      </h1>

      {loadFailed ? (
        <p role="alert" className="text-[13px] text-red-700">
          Couldn&apos;t load this asset. Check your connection, then refresh the page.
        </p>
      ) : original === undefined ? (
        <p role="status" className="py-10 text-center text-[13px] text-muted">
          Loading asset…
        </p>
      ) : original === null || values === null ? (
        <p role="alert" className="text-[13px] text-red-700">
          Asset not found. It may have been deleted, or it is not in this workspace.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <section className="flex flex-col gap-3.5 rounded-[14px] border border-border bg-surface p-4">
            <h2 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">
              Asset Information
            </h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-x-4 md:gap-y-3.5">
              <Field id="name" label="Product Name" required wide>
                {input("name", { required: true })}
              </Field>
              <Field id="serial_number" label="Serial Number" required>
                {input("serial_number", { required: true })}
              </Field>
              <Field id="purchase_date" label="Purchase Date" required>
                {input("purchase_date", { type: "date", required: true })}
              </Field>
              <Field id="vendor_name" label="Vendor" required>
                {input("vendor_name", { required: true })}
              </Field>
              <Field id="category_name" label="Category" required>
                {input("category_name", { required: true })}
              </Field>
              <Field id="invoice_number" label="Invoice Number" required>
                {input("invoice_number", { required: true })}
              </Field>
              <Field id="price" label="Price" required>
                {input("price", { type: "number", min: 0, step: "0.01", inputMode: "decimal", required: true })}
              </Field>
            </div>
          </section>

          <section className="flex flex-col gap-3.5 rounded-[14px] border border-border bg-surface p-4">
            <h2 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">Warranty</h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-x-4 md:gap-y-3.5">
              <Field id="warranty_provider" label="Warranty Provider" required wide>
                {input("warranty_provider", { required: true })}
              </Field>
              <Field id="warranty_start_date" label="Start Date" required>
                {input("warranty_start_date", { type: "date", required: true })}
              </Field>
              <Field id="warranty_duration_months" label="Duration (months)" required>
                {input("warranty_duration_months", { type: "number", min: 1, max: 600, step: 1, required: true })}
              </Field>
            </div>
          </section>

          <section className="flex flex-col gap-3.5 rounded-[14px] border border-border bg-surface p-4">
            <h2 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">Box / Storage</h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-x-4 md:gap-y-3.5">
              <Field id="location_name" label="Storage Location">
                {input("location_name")}
              </Field>
              <Field id="storage_note" label="Note">
                {input("storage_note")}
              </Field>
            </div>
          </section>

          {error && (
            <p role="alert" className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
              {error}
            </p>
          )}

          <div className="flex flex-col gap-3 md:flex-row-reverse">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
            <Button variant="secondary" disabled={saving} onClick={() => router.push(detailHref)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
