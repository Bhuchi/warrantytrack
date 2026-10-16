import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export interface WorkspaceStat {
  value: string;
  label: string;
}

interface WorkspaceCardProps {
  title: string;
  /** Long description, desktop only. */
  description: string;
  /** Condensed description used on mobile, where space is tight. */
  descriptionShort: string;
  icon: ReactNode;
  stats: WorkspaceStat[];
  /** Where the desktop "Continue" goes. Mobile uses one shared button instead. */
  href: string;
  selected: boolean;
  onSelect: () => void;
}

/**
 * One workspace choice — Figma D03 (3344:20 / 3344:41) and M03 (3382:90 / 3382:109).
 *
 * The header row reflows between breakpoints: mobile puts the icon, text and
 * state indicator on one line; desktop puts the icon and indicator on the first
 * line and drops the text underneath. That is `md:flex-wrap` plus `md:order-last`
 * on the text block, rather than two copies of the markup.
 */
export default function WorkspaceCard({
  title,
  description,
  descriptionShort,
  icon,
  stats,
  href,
  selected,
  onSelect,
}: WorkspaceCardProps) {
  return (
    <div
      className={`flex flex-col gap-4 rounded-2xl bg-surface p-5 md:flex-1 md:gap-[22px] md:px-8 md:pt-8 md:pb-7 ${
        selected
          ? "border-2 border-brand md:shadow-panel-selected"
          : "border border-border md:shadow-panel"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className="flex flex-col gap-4 text-left md:gap-[22px]"
      >
        <div className="flex w-full items-center gap-3.5 md:flex-wrap md:justify-between md:gap-y-[22px]">
          <span
            className={`flex size-[50px] shrink-0 items-center justify-center rounded-[13px] md:size-14 md:rounded-[14px] ${
              selected
                ? "bg-brand text-brand-foreground"
                : "bg-brand-subtle text-brand"
            }`}
          >
            {icon}
          </span>

          <div className="flex min-w-px flex-1 flex-col gap-1 md:order-last md:w-full md:flex-none md:gap-2">
            <h2 className="text-[19px] font-bold tracking-[-0.38px] text-foreground md:text-[24px] md:tracking-[-0.48px]">
              {title}
            </h2>
            <p className="text-[13px] leading-[19px] tracking-[-0.26px] text-muted md:hidden">
              {descriptionShort}
            </p>
            <p className="hidden text-[15px] leading-6 tracking-[-0.3px] text-muted md:block">
              {description}
            </p>
          </div>

          {selected ? (
            <span className="flex size-[26px] shrink-0 items-center justify-center rounded-full bg-brand-subtle text-[12px] font-semibold tracking-[-0.24px] text-brand md:size-auto md:gap-1.5 md:py-1.5 md:pr-3 md:pl-2.5">
              <Image
                src="/icons/check-badge.svg"
                alt=""
                width={14}
                height={14}
              />
              <span className="hidden md:inline">Selected</span>
            </span>
          ) : (
            <Image
              src="/icons/chevron-right.svg"
              alt=""
              width={22}
              height={22}
              className="size-5 shrink-0 md:size-[22px]"
            />
          )}
        </div>

        <span className="h-px w-full bg-border" />

        <div className="flex gap-7 md:gap-6">
          {stats.map((stat) => (
            <span key={stat.label} className="flex flex-col gap-[3px] md:gap-1">
              <span className="text-[19px] font-bold text-brand md:text-[20px]">
                {stat.value}
              </span>
              <span className="text-[11px] tracking-[-0.22px] text-muted-light md:text-[12px] md:tracking-[-0.24px]">
                {stat.label}
              </span>
            </span>
          ))}
        </div>
      </button>

      <Link
        href={href}
        className={`hidden h-[50px] w-full items-center justify-center rounded-lg text-[16px] font-bold tracking-[-0.32px] md:flex ${
          selected
            ? "bg-brand text-brand-foreground"
            : "border border-border text-brand"
        }`}
      >
        Continue
      </Link>
    </div>
  );
}
