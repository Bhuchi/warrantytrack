"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import Card from "@/components/Card";
import { ChevronDownIcon } from "@/components/NavIcons";
import StatusBadge from "@/components/StatusBadge";
import { formatDate } from "@/features/dashboard/format";
import type { WarrantyStatus } from "@/types";
import type { AssetListItem, AssetListResponse } from "@/types/assetList";

import { getAssets } from "./getAssets";

type StatusFilter = WarrantyStatus | "all";

/** Mobile tabs, as in M05 (3382:365). */
const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "expiring_soon", label: "Expiring" },
  { value: "expired", label: "Expired" },
];

/**
 * Desktop dropdown (D05 3354:116): the same choices as the tabs. No "No
 * warranty": every asset must have a warranty now (issue #34).
 */
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All statuses" },
  ...STATUS_TABS.slice(1),
];

/** Figma has five device icons; other categories fall back to the monitor, as the Accessory row does in D05. */
const CATEGORY_ICONS: Record<string, string> = {
  Laptop: "/icons/device-laptop.svg",
  Camera: "/icons/device-camera.svg",
  Mobile: "/icons/device-mobile.svg",
  Tablet: "/icons/device-mobile.svg",
  Printer: "/icons/device-printer.svg",
};

function iconFor(category: string | null | undefined): string {
  return (category && CATEGORY_ICONS[category]) || "/icons/device-monitor.svg";
}

/** "19 May 2026", or "—" for an asset with no warranty. */
function expiryLabel(item: AssetListItem): string {
  return item.warranty_end_date ? formatDate(item.warranty_end_date) : "—";
}

/**
 * Search, status filter and the list itself. Mobile M05 (3382:296) shows
 * cards; desktop D05 (3354:2) shows a table. Rows open Asset Detail
 * (CLOUDAPPG5-88), which 404s until that page exists.
 *
 * TODO: Category / Location dropdowns, Export CSV, the row menu and the
 * mobile filter button need backend lists that do not exist yet.
 * TODO: swap the empty and loading messages for Skeleton / EmptyState from
 * FE-03 (CLOUDAPPG5-121) once they exist.
 */
export default function AssetsList() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  // The last answer, tagged with the filters it was for.
  const [loaded, setLoaded] = useState<{ key: string; data: AssetListResponse } | null>(null);
  // The filters whose request failed, e.g. the API was not running.
  const [failedKey, setFailedKey] = useState<string | null>(null);

  const key = `${search}|${status}|${page}`;
  const failed = failedKey === key;
  const loading = loaded?.key !== key;
  const data = loaded?.data ?? null;

  // Ask again whenever the search, status or page changes. `ignore` drops an
  // older answer that arrives after a newer request was sent.
  useEffect(() => {
    let ignore = false;
    getAssets({
      q: search.trim() || undefined,
      status: status === "all" ? undefined : status,
      page,
    })
      .then((result) => {
        if (!ignore) setLoaded({ key, data: result });
      })
      .catch(() => {
        if (!ignore) setFailedKey(key);
      });
    return () => {
      ignore = true;
    };
  }, [key, search, status, page]);

  /** A new search or filter starts again at page 1. */
  function changeSearch(next: string) {
    setSearch(next);
    setPage(1);
  }
  function changeStatus(next: StatusFilter) {
    setStatus(next);
    setPage(1);
  }

  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  // "Showing 21–25": the row numbers of the first and last row on this page.
  const firstShown = data ? (data.page - 1) * data.page_size + 1 : 0;
  const lastShown = data ? firstShown + data.items.length - 1 : 0;
  const filtered = search.trim() !== "" || status !== "all";

  return (
    <div className="flex flex-col gap-3 md:gap-4">
      {/* Mobile: search then tabs. Desktop: one white bar with search and the Status dropdown. */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:rounded-[14px] md:border md:border-border md:bg-surface md:px-5 md:py-4">
        <label className="flex h-[46px] items-center gap-2.5 rounded-[10px] border border-border bg-surface px-3.5 md:h-11 md:flex-1 md:rounded-lg md:bg-canvas">
          <Image src="/icons/search.svg" alt="" width={17} height={17} className="shrink-0" />
          <span className="sr-only">Search assets</span>
          <input
            type="search"
            value={search}
            onChange={(event) => changeSearch(event.target.value)}
            placeholder="Search assets, serial or invoice…"
            className="min-w-0 flex-1 bg-transparent text-[14px] tracking-[-0.28px] text-foreground outline-none placeholder:text-muted-light"
          />
        </label>

        <div className="flex gap-2 overflow-x-auto md:hidden">
          {STATUS_TABS.map((tab) => {
            const selected = status === tab.value;
            return (
              <button
                key={tab.value}
                type="button"
                aria-pressed={selected}
                onClick={() => changeStatus(tab.value)}
                className={`shrink-0 rounded-full px-3.5 py-2 text-[12px] font-semibold tracking-[-0.24px] ${
                  selected ? "bg-brand text-brand-foreground" : "border border-border bg-surface text-muted"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <label className="hidden h-11 w-[178px] shrink-0 items-center gap-2.5 rounded-lg border border-border bg-surface pr-3 pl-3.5 md:flex">
          <span className="flex min-w-0 flex-1 flex-col gap-px">
            <span className="text-[10px] tracking-[0.2px] text-muted-light">STATUS</span>
            <select
              value={status}
              onChange={(event) => changeStatus(event.target.value as StatusFilter)}
              className="appearance-none bg-transparent text-[13px] font-semibold tracking-[-0.26px] text-foreground outline-none"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </span>
          <ChevronDownIcon className="size-4 shrink-0 text-muted-light" />
        </label>
      </div>

      {failed ? (
        <Card className="flex flex-col items-center gap-1 px-4 py-10 text-center">
          <p className="text-[14px] font-semibold text-foreground">Couldn&apos;t load assets.</p>
          <p className="text-[13px] text-muted">Check your connection, then refresh the page.</p>
        </Card>
      ) : !data ? (
        <p className="py-10 text-center text-[13px] text-muted">Loading assets…</p>
      ) : data.items.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 px-4 py-10 text-center">
          <p className="text-[14px] font-semibold text-foreground">
            {filtered ? "No assets match your search." : "No assets yet."}
          </p>
          {filtered && (
            <button
              type="button"
              onClick={() => {
                changeSearch("");
                changeStatus("all");
              }}
              className="text-[13px] font-semibold text-brand"
            >
              Clear search and filters
            </button>
          )}
        </Card>
      ) : (
        // Dimmed while a newer answer is on its way.
        <div className={`flex flex-col gap-3 transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {/* Mobile: one card per asset (M05 3382:375). */}
          <ul className="flex flex-col gap-2.5 md:hidden">
            {data.items.map((item) => (
              <li key={item.id}>
                <Link
                  href={`/assets/${item.id}`}
                  className="flex items-center gap-3 rounded-xl border border-border bg-surface py-3 pr-3 pl-3.5"
                >
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-subtle">
                    <Image src={iconFor(item.category_name)} alt="" width={19} height={19} />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate text-[14px] font-semibold tracking-[-0.28px] text-foreground">
                      {item.name}
                    </span>
                    <span className="truncate text-[11px] tracking-[-0.22px] text-muted-light">
                      {item.serial_number}
                      {item.warranty_end_date && ` · ${formatDate(item.warranty_end_date)}`}
                    </span>
                  </span>
                  <StatusBadge status={item.warranty_status} />
                  <ChevronDownIcon className="size-[15px] shrink-0 -rotate-90 text-muted-light" />
                </Link>
              </li>
            ))}
          </ul>

          {/* Desktop: the table (D05 3354:128). */}
          <Card className="hidden px-6 pt-1.5 pb-[18px] md:block">
            <table className="w-full table-fixed">
              <thead>
                <tr className="text-left text-[11px] font-semibold tracking-[0.44px] text-muted-light">
                  <th className="w-[32%] pt-4 pb-3.5 font-semibold">ASSET</th>
                  <th className="w-[12%] pt-4 pb-3.5 font-semibold">CATEGORY</th>
                  <th className="w-[12%] pt-4 pb-3.5 font-semibold">VENDOR</th>
                  <th className="w-[14%] pt-4 pb-3.5 font-semibold">LOCATION</th>
                  <th className="w-[15%] pt-4 pb-3.5 font-semibold">WARRANTY</th>
                  <th className="w-[15%] pt-4 pb-3.5 font-semibold">EXPIRY DATE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border border-t border-border text-[14px] font-medium tracking-[-0.28px] text-foreground">
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td className="py-[13px] pr-4">
                      <Link href={`/assets/${item.id}`} className="flex items-center gap-3">
                        <span className="flex size-[38px] shrink-0 items-center justify-center rounded-[9px] bg-brand-subtle">
                          <Image src={iconFor(item.category_name)} alt="" width={18} height={18} />
                        </span>
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <span className="truncate font-semibold">{item.name}</span>
                          <span className="truncate text-[11px] font-normal tracking-[-0.22px] text-muted-light">
                            {item.serial_number}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td className="truncate pr-4">{item.category_name ?? "—"}</td>
                    <td className="truncate pr-4">{item.vendor_name ?? "—"}</td>
                    <td className="truncate pr-4">{item.location ?? "—"}</td>
                    <td className="pr-4">
                      <StatusBadge status={item.warranty_status} />
                    </td>
                    <td>{expiryLabel(item)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {/* Paging, on both sizes. */}
          <div className="flex flex-col items-center gap-3 md:flex-row md:justify-between">
            <p className="text-[13px] tracking-[-0.26px] text-muted">
              Showing {firstShown}–{lastShown} of {data.total} assets
            </p>
            {pageCount > 1 && (
              <nav aria-label="Pages" className="flex items-center gap-2">
                <button
                  type="button"
                  aria-label="Previous page"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                  className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-muted disabled:opacity-40"
                >
                  <ChevronDownIcon className="size-4 rotate-90" />
                </button>
                {Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => (
                  <button
                    key={number}
                    type="button"
                    aria-current={number === page ? "page" : undefined}
                    onClick={() => setPage(number)}
                    className={`flex size-9 items-center justify-center rounded-lg text-[13px] font-semibold ${
                      number === page ? "bg-brand text-brand-foreground" : "border border-border bg-surface text-foreground"
                    }`}
                  >
                    {number}
                  </button>
                ))}
                <button
                  type="button"
                  aria-label="Next page"
                  disabled={page === pageCount}
                  onClick={() => setPage(page + 1)}
                  className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-muted disabled:opacity-40"
                >
                  <ChevronDownIcon className="size-4 -rotate-90" />
                </button>
              </nav>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
