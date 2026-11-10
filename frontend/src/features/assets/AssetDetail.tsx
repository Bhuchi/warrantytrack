"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import type { WarrantyStatus } from "@/types";
import type { AssetDetail as Asset } from "@/types/assets";

import { getAsset } from "./getAsset";

const DAY_MS = 24 * 60 * 60 * 1000;

type Warranty = NonNullable<Asset["warranty"]>;
type Document = Asset["documents"][number];

/** What the status pill says for each warranty status from the API. */
const STATUS_LABELS: Record<WarrantyStatus, string> = {
  active: "Active",
  expiring_soon: "Expiring Soon",
  expired: "Expired",
  unknown: "No warranty",
};

const DOCUMENT_KINDS: Record<Document["kind"], string> = {
  invoice: "Invoice",
  receipt: "Receipt",
  warranty_card: "Warranty card",
  other: "Document",
};

function toUtcDay(date: string): number {
  const [year, month, day] = date.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

function daysBetween(start: string, end: string): number {
  return Math.ceil((toUtcDay(end) - toUtcDay(start)) / DAY_MS);
}

function getBangkokDate(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Bangkok",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
}

/** "19 May 2026", or "—" when there is no date. */
function formatDate(date: string | null | undefined): string {
  if (!date) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

/** "฿51,599.00", or "—" when there is no price. */
function formatPrice(price: string | null, currency: string): string {
  if (price === null) return "—";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
  }).format(Number(price));
}

/**
 * Days left and how full the bar is. The status itself comes from the API;
 * this is only for the countdown. Without a start date the bar is empty.
 */
function getCountdown(warranty: Warranty) {
  const today = getBangkokDate(new Date());
  const daysRemaining = Math.max(0, daysBetween(today, warranty.end_date));
  const duration = warranty.start_date ? daysBetween(warranty.start_date, warranty.end_date) : 0;
  const progress =
    duration > 0 ? Math.min(100, Math.max(0, Math.round((daysRemaining / duration) * 100))) : 0;
  return { daysRemaining, progress };
}

function statusClasses(status: WarrantyStatus) {
  if (status === "expired") return "bg-red-100 text-red-700";
  if (status === "expiring_soon") return "bg-amber-100 text-amber-700";
  if (status === "unknown") return "bg-canvas text-muted";
  return "bg-green-100 text-green-700";
}

/** The file name at the end of an S3 key: "workspace/abc/receipt.pdf" → "receipt.pdf". */
function fileName(s3Key: string): string {
  return s3Key.split("/").pop() || s3Key;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 text-[13px] tracking-[-0.26px]">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-semibold text-foreground">{value}</dd>
    </div>
  );
}

function Panel({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const headingId = `${title.toLowerCase().replace(/ /g, "-")}-heading`;
  return (
    <section
      aria-labelledby={headingId}
      className={`flex w-full flex-col gap-[13px] rounded-[14px] border border-border bg-surface p-4 ${className}`}
    >
      <h2
        id={headingId}
        className="text-[15px] font-bold leading-[normal] tracking-[-0.3px] text-foreground"
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function ProductSummary({ asset }: { asset: Asset }) {
  const status = asset.warranty?.status ?? "unknown";
  // "Apple · Laptop", leaving out whichever is missing.
  const subtitle = [asset.vendor?.name, asset.category?.name].filter(Boolean).join(" · ");

  return (
    <section className="flex w-full items-center gap-[14px] rounded-[14px] border border-border bg-surface p-4">
      <span className="flex size-16 shrink-0 items-center justify-center rounded-xl bg-brand-subtle">
        <Image src="/icons/asset-product.svg" alt="" width={30} height={30} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-[7px]">
        <h1 className="w-full text-[17px] font-bold leading-[23px] tracking-[-0.34px] text-foreground">
          {asset.name}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-[9px] py-1 text-[10px] font-semibold tracking-[-0.2px] ${statusClasses(status)}`}
          >
            {STATUS_LABELS[status]}
          </span>
          {subtitle && (
            <span className="text-xs tracking-[-0.24px] text-muted">{subtitle}</span>
          )}
        </div>
      </div>
    </section>
  );
}

function WarrantyCountdown({ warranty }: { warranty: Warranty }) {
  const { daysRemaining, progress } = getCountdown(warranty);
  const expired = warranty.status === "expired";

  return (
    <section
      aria-label="Warranty countdown"
      className="flex w-full flex-col gap-3 rounded-[14px] border border-border bg-surface p-4"
    >
      <div className="flex w-full items-center gap-[14px]">
        <span
          className={`flex size-12 shrink-0 items-center justify-center rounded-xl ${expired ? "bg-red-100" : "bg-green-100"}`}
        >
          <Image
            src="/icons/asset-warranty.svg"
            alt=""
            width={24}
            height={24}
          />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
            <div className="flex items-baseline gap-1.5">
              <span
                className={`text-[26px] font-bold leading-none tracking-[-0.78px] ${expired ? "text-red-700" : "text-green-600"}`}
              >
                {daysRemaining}
              </span>
              <span className="text-[13px] font-semibold tracking-[-0.26px] text-foreground">
                days remaining
              </span>
            </div>
            <time
              dateTime={warranty.end_date}
              className="text-[13px] font-semibold tracking-[-0.26px] text-muted-light"
            >
              {formatDate(warranty.end_date)}
            </time>
          </div>
          <p className="mt-1 text-[11px] tracking-[-0.22px] text-muted">
            {warranty.provider ?? "Warranty"} · expires {formatDate(warranty.end_date)}
          </p>
        </div>
      </div>
      <div
        role="progressbar"
        aria-label="Warranty time remaining"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        className="h-[7px] w-full overflow-hidden rounded-full bg-border"
      >
        <div
          className={`h-full rounded-full ${expired ? "bg-red-600" : "bg-green-600"}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </section>
  );
}

function DocumentRow({ document }: { document: Document }) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-surface px-[14px] py-[13px]">
      <span className="flex size-[38px] shrink-0 items-center justify-center rounded-[9px] bg-brand-subtle">
        <Image src="/icons/asset-document.svg" alt="" width={18} height={18} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold tracking-[-0.26px] text-foreground">
          {fileName(document.s3_key)}
        </p>
        <p className="text-[11px] text-muted-light">
          {DOCUMENT_KINDS[document.kind]} · stored in S3
        </p>
      </div>
      {/* TODO: make this a download link once the API hands out presigned GET URLs. */}
      <Image src="/icons/asset-download.svg" alt="" width={17} height={17} />
    </div>
  );
}

function StoragePanel({ asset }: { asset: Asset }) {
  return (
    <Panel title="Box / Storage">
      <div className="flex flex-col gap-3 sm:flex-row md:flex-col lg:flex-row">
        <div
          role="img"
          aria-label="No storage photo attached"
          className="flex h-28 w-full shrink-0 items-center justify-center rounded-[10px] border border-dashed border-border bg-canvas text-xs text-muted sm:w-36 md:w-full lg:w-36"
        >
          No photo attached
        </div>
        <dl className="flex min-w-0 flex-1 flex-col gap-2">
          <div>
            <dt className="text-[11px] text-muted">Storage location</dt>
            <dd className="text-[13px] font-semibold text-foreground">
              {asset.location?.name ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] text-muted">Note</dt>
            <dd className="text-[13px] leading-5 text-foreground">
              {asset.storage_note ?? "—"}
            </dd>
          </div>
        </dl>
      </div>
    </Panel>
  );
}

function QuickActions() {
  return (
    <div className="flex w-full flex-col gap-3">
      <button
        type="button"
        aria-disabled="true"
        title="Asset editing will be connected in a later task"
        className="flex h-[54px] w-full items-center justify-center gap-2.5 rounded-[10px] bg-brand text-base font-bold tracking-[-0.32px] text-brand-foreground"
      >
        <Image src="/icons/asset-edit.svg" alt="" width={17} height={17} />
        Edit Asset
      </button>
      <Link
        href="/assets/new"
        className="flex h-[54px] w-full items-center justify-center gap-2.5 rounded-[10px] bg-brand text-base font-bold tracking-[-0.32px] text-brand-foreground"
      >
        <Image src="/icons/asset-add.svg" alt="" width={17} height={17} />
        Add Asset
      </Link>
    </div>
  );
}

/** Not found, couldn't load: a message with a way back to the list. */
function Message({ title, body }: { title: string; body: string }) {
  return (
    <section className="flex flex-col items-center gap-1 rounded-[14px] border border-border bg-surface px-4 py-10 text-center">
      <h1 className="text-[15px] font-bold text-foreground">{title}</h1>
      <p className="text-[13px] text-muted">{body}</p>
    </section>
  );
}

/**
 * Asset Detail (D08). Loads the asset from GET /assets/{id} in the browser.
 *
 * `undefined` = still loading, `null` = not found (404), otherwise the asset.
 */
export default function AssetDetail({ assetId }: { assetId: string }) {
  const [asset, setAsset] = useState<Asset | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let ignore = false;
    getAsset(assetId)
      .then((result) => {
        if (!ignore) setAsset(result);
      })
      .catch(() => {
        if (!ignore) setFailed(true);
      });
    return () => {
      ignore = true;
    };
  }, [assetId]);

  return (
    <div className="min-h-screen bg-canvas">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-4 md:gap-4 md:px-8 md:pt-8 lg:px-12">
        <Link
          href="/assets"
          className="flex w-fit items-center gap-1.5 text-[13px] font-semibold tracking-[-0.26px] text-muted hover:text-brand"
        >
          <Image src="/icons/asset-back.svg" alt="" width={15} height={15} />
          Assets
        </Link>

        {failed ? (
          <Message
            title="Couldn't load this asset."
            body="Check your connection, then refresh the page."
          />
        ) : asset === undefined ? (
          <p className="py-10 text-center text-[13px] text-muted">Loading asset…</p>
        ) : asset === null ? (
          <Message
            title="Asset not found."
            body="It may have been deleted, or it is not in this workspace."
          />
        ) : (
          <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)] md:gap-5">
            <div className="flex min-w-0 flex-col gap-3 md:gap-4">
              <ProductSummary asset={asset} />
              {asset.warranty && <WarrantyCountdown warranty={asset.warranty} />}

              <Panel title="Asset Information">
                <dl className="flex flex-col gap-[11px]">
                  <DetailRow label="Serial Number" value={asset.serial_number} />
                  <DetailRow label="Purchase Date" value={formatDate(asset.purchase_date)} />
                  <DetailRow label="Expiry Date" value={formatDate(asset.warranty?.end_date)} />
                  <DetailRow label="Price" value={formatPrice(asset.price, asset.currency)} />
                  <DetailRow label="Invoice" value={asset.invoice_number ?? "—"} />
                  <DetailRow label="Category" value={asset.category?.name ?? "—"} />
                </dl>
              </Panel>
            </div>

            <div className="flex min-w-0 flex-col gap-3 md:gap-4">
              <Panel title="Linked Documents">
                {asset.documents.length > 0 ? (
                  asset.documents.map((document) => (
                    <DocumentRow key={document.id} document={document} />
                  ))
                ) : (
                  <p className="text-[13px] text-muted">No documents attached.</p>
                )}
              </Panel>
              <StoragePanel asset={asset} />
              <QuickActions />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
