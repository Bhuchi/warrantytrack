import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

const DAY_MS = 24 * 60 * 60 * 1000;

const asset = {
  name: "MacBook Pro 14-inch (M3)",
  brand: "Apple",
  category: "Laptop",
  serialNumber: "C02X1234ABC",
  purchaseDate: "2025-10-27",
  price: "฿ 51,599.00",
  invoiceNumber: "INV-2025-1027",
  warrantyProvider: "Apple Limited Warranty",
  warrantyStartDate: "2025-10-27",
  warrantyExpiryDate: "2027-10-27",
  invoiceFile: "Invoice_INV-2025-1027.pdf",
  invoiceSize: "1.2 MB",
  storageLocation: "Home office · shelf 2",
  storageNote: "Original packaging is stored on the top shelf.",
} as const;

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

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

function getWarrantyDetails() {
  const today = getBangkokDate(new Date());
  const daysRemaining = daysBetween(today, asset.warrantyExpiryDate);
  const warrantyDuration = daysBetween(
    asset.warrantyStartDate,
    asset.warrantyExpiryDate,
  );
  const progress = Math.min(
    100,
    Math.max(0, Math.round((Math.max(daysRemaining, 0) / warrantyDuration) * 100)),
  );

  if (daysRemaining <= 0) {
    return { daysRemaining: 0, progress, status: "Expired" as const };
  }
  if (daysRemaining <= 30) {
    return { daysRemaining, progress, status: "Expiring Soon" as const };
  }
  return { daysRemaining, progress, status: "Active" as const };
}

function statusClasses(status: "Active" | "Expiring Soon" | "Expired") {
  if (status === "Expired") return "bg-red-100 text-red-700";
  if (status === "Expiring Soon") return "bg-amber-100 text-amber-700";
  return "bg-green-100 text-green-700";
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

function AssetHeader() {
  return (
    <header className="flex h-[60px] items-center justify-between border-b border-border bg-surface px-4 md:h-20 md:px-8 lg:px-12">
      <div className="flex items-center gap-3">
        <Link
          href="/workspace"
          aria-label="Go to workspace"
          className="flex size-9 items-center justify-center rounded-lg"
        >
          <Image src="/icons/asset-menu.svg" alt="" width={22} height={22} />
        </Link>
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/icons/asset-logo.svg"
            alt=""
            width={36}
            height={36}
          />
          <span className="text-[17px] font-bold text-brand md:text-[22px]">
            WarrantyTrack
          </span>
        </Link>
      </div>
      <div className="flex items-center gap-2.5">
        <Image
          src="/icons/asset-bell.svg"
          alt="Notifications"
          width={36}
          height={36}
        />
        <span className="flex size-9 items-center justify-center rounded-full bg-brand-subtle text-xs font-bold text-brand">
          CA
        </span>
      </div>
    </header>
  );
}

function ProductSummary({ status }: { status: "Active" | "Expiring Soon" | "Expired" }) {
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
            {status}
          </span>
          <span className="text-xs tracking-[-0.24px] text-muted">
            {asset.brand} · {asset.category}
          </span>
        </div>
      </div>
    </section>
  );
}

function WarrantyCountdown({
  daysRemaining,
  progress,
}: {
  daysRemaining: number;
  progress: number;
}) {
  const expired = daysRemaining === 0;
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
              dateTime={asset.warrantyExpiryDate}
              className="text-[13px] font-semibold tracking-[-0.26px] text-muted-light"
            >
              {formatDate(asset.warrantyExpiryDate)}
            </time>
          </div>
          <p className="mt-1 text-[11px] tracking-[-0.22px] text-muted">
            {asset.warrantyProvider} · expires {formatDate(asset.warrantyExpiryDate)}
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

function DocumentRow() {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-surface px-[14px] py-[13px]">
      <span className="flex size-[38px] shrink-0 items-center justify-center rounded-[9px] bg-brand-subtle">
        <Image src="/icons/asset-document.svg" alt="" width={18} height={18} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold tracking-[-0.26px] text-foreground">
          {asset.invoiceFile}
        </p>
        <p className="text-[11px] text-muted-light">
          {asset.invoiceSize} · stored in S3
        </p>
      </div>
      <Image
        src="/icons/asset-download.svg"
        alt="Download invoice"
        width={17}
        height={17}
      />
    </div>
  );
}

function StoragePanel() {
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
              {asset.storageLocation}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] text-muted">Note</dt>
            <dd className="text-[13px] leading-5 text-foreground">
              {asset.storageNote}
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
      <button
        type="button"
        aria-disabled="true"
        title="Asset creation will be connected in a later task"
        className="flex h-[54px] w-full items-center justify-center gap-2.5 rounded-[10px] bg-brand text-base font-bold tracking-[-0.32px] text-brand-foreground"
      >
        <Image src="/icons/asset-add.svg" alt="" width={17} height={17} />
        Add Asset
      </button>
    </div>
  );
}

export default function AssetDetail({ assetId }: { assetId: string }) {
  const warranty = getWarrantyDetails();
  const status = warranty.status;

  return (
    <div className="min-h-screen bg-canvas" data-asset-id={assetId}>
      <AssetHeader />
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-4 md:gap-4 md:px-8 md:pt-8 lg:px-12">
        <Link
          href="/workspace"
          className="flex w-fit items-center gap-1.5 text-[13px] font-semibold tracking-[-0.26px] text-muted hover:text-brand"
        >
          <Image src="/icons/asset-back.svg" alt="" width={15} height={15} />
          Assets
        </Link>

        <section
          aria-label="Asset setup status"
          className="flex w-full flex-col gap-2.5 rounded-xl border border-border bg-surface px-4 py-[13px]"
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-[13px] font-semibold tracking-[-0.26px] text-brand">
              Step 3 of 3 · OCR Review
            </p>
            <p className="text-xs font-bold text-muted-light">Complete</p>
          </div>
          <div
            role="progressbar"
            aria-label="Asset setup completed"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={100}
            className="h-1.5 w-full overflow-hidden rounded-full bg-border"
          >
            <div className="h-full w-full rounded-full bg-brand" />
          </div>
        </section>

        <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)] md:gap-5">
          <div className="flex min-w-0 flex-col gap-3 md:gap-4">
            <ProductSummary status={status} />
            <WarrantyCountdown
              daysRemaining={warranty.daysRemaining}
              progress={warranty.progress}
            />

            <Panel title="Asset Information">
              <dl className="flex flex-col gap-[11px]">
                <DetailRow label="Serial Number" value={asset.serialNumber} />
                <DetailRow
                  label="Purchase Date"
                  value={formatDate(asset.purchaseDate)}
                />
                <DetailRow
                  label="Expiry Date"
                  value={formatDate(asset.warrantyExpiryDate)}
                />
                <DetailRow label="Price" value={asset.price} />
                <DetailRow label="Invoice" value={asset.invoiceNumber} />
                <DetailRow label="Category" value={asset.category} />
              </dl>
            </Panel>
          </div>

          <div className="flex min-w-0 flex-col gap-3 md:gap-4">
            <Panel title="Linked Documents">
              <DocumentRow />
            </Panel>
            <StoragePanel />
            <QuickActions />
          </div>
        </div>
      </main>
    </div>
  );
}
