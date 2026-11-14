"use client";

import Image from "next/image";
import Link from "next/link";

import { BellIcon, MenuIcon } from "@/components/NavIcons";

/**
 * Top bar for signed-in screens — Figma App Bar 3396:7004.
 *
 * Mobile only: the hamburger opens the navigation drawer. From md up the
 * navigation is pinned beside the content, so the whole bar is hidden.
 */

interface AppBarProps {
  onMenuClick: () => void;
  /** Avatar initials for the signed-in user. */
  initials: string;
  unreadCount: number;
}

export default function AppBar({
  onMenuClick,
  initials,
  unreadCount,
}: AppBarProps) {
  return (
    <header className="flex h-[60px] items-center justify-between border-b border-border bg-surface px-4 md:hidden">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="flex size-9 items-center justify-center rounded-lg text-foreground"
        >
          <MenuIcon className="size-[22px]" />
        </button>

        <Image src="/warranty-logo-blue.svg" alt="" width={36} height={36} />
        <span className="text-[17px] font-bold text-brand">WarrantyTrack</span>
      </div>

      <div className="flex items-center gap-2.5">
        <Link
          href="/notifications"
          prefetch={false}
          aria-label={
            unreadCount > 0
              ? `Notifications, ${unreadCount} unread`
              : "Notifications"
          }
          className="relative flex size-9 items-center justify-center rounded-[9px] bg-canvas text-muted"
        >
          <BellIcon className="size-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-px -right-px size-[9px] rounded-full bg-danger" />
          )}
        </Link>

        <span className="flex size-9 items-center justify-center rounded-full bg-brand-subtle text-[12px] font-bold text-brand">
          {initials}
        </span>
      </div>
    </header>
  );
}
