"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import {
  AddAssetIcon,
  AssetsIcon,
  BellIcon,
  ChevronDownIcon,
  CloseIcon,
  DashboardIcon,
  SettingsIcon,
  SignOutIcon,
} from "@/components/NavIcons";

/**
 * Navigation panel — Figma M10 (3392:2 organization, 3455:536 personal),
 * built from the Nav bar component 3396:7135.
 *
 * Mobile: a drawer that slides in over the page and is dismissed by the close
 * button, the backdrop, or Escape.
 * Desktop: the same panel, pinned open beside the content.
 *
 * TODO: the desktop sidebar has its own frame (3382:1309, 260px). Check it when
 * building D04 — this currently reuses the mobile panel at a narrower width.
 */

const MENU = [
  { href: "/dashboard", label: "Dashboard", Icon: DashboardIcon },
  { href: "/assets", label: "Assets", Icon: AssetsIcon },
  { href: "/assets/new", label: "Add Asset", Icon: AddAssetIcon },
  { href: "/notifications", label: "Notifications", Icon: BellIcon },
  { href: "/settings", label: "Settings", Icon: SettingsIcon },
] as const;

export interface NavWorkspace {
  name: string;
  /** "Personal workspace" or "Organization workspace". */
  kind: string;
  initials: string;
}

export interface NavUser {
  name: string;
  department: string;
  initials: string;
}

interface NavPanelProps {
  open: boolean;
  onClose: () => void;
  workspace: NavWorkspace;
  /** Organization workspaces show a user card; personal ones do not. */
  user: NavUser | null;
  unreadCount: number;
}

export default function NavPanel({
  open,
  onClose,
  workspace,
  user,
  unreadCount,
}: NavPanelProps) {
  // usePathname tells us the URL being viewed, so the matching item can be
  // highlighted without every page passing its own name down.
  const pathname = usePathname();
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // useEffect runs after render. This one wires a keyboard listener while the
  // drawer is open, and the function it returns removes the listener again —
  // without that cleanup, a listener would pile up every time it opened.
  useEffect(() => {
    if (!open) return;

    closeButtonRef.current?.focus();
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <aside
      // Hidden from assistive tech on mobile while closed, but always present
      // on desktop where it is pinned open.
      aria-label="Main navigation"
      className={`fixed inset-y-0 left-0 z-40 flex w-[304px] shrink-0 flex-col justify-between bg-surface px-5 pt-5 pb-6 shadow-drawer transition-transform duration-200 md:static md:z-auto md:w-[260px] md:translate-x-0 md:shadow-none md:ring-1 md:ring-border ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div className="flex flex-col gap-[22px]">
        <div className="flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <Image
              src="/warranty-logo-blue.svg"
              alt=""
              width={36}
              height={36}
            />
            <span className="text-[18px] font-bold text-brand">
              WarrantyTrack
            </span>
          </Link>

          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="flex size-[34px] items-center justify-center rounded-lg bg-canvas text-muted md:hidden"
          >
            <CloseIcon className="size-[18px]" />
          </button>
        </div>

        <Link
          href="/workspace"
          onClick={onClose}
          aria-label={`${workspace.name}, ${workspace.kind}. Switch workspace`}
          className="flex w-full items-center gap-2.5 rounded-[10px] border border-border bg-canvas px-3 py-[11px] text-left hover:border-brand"
        >
          <span className="flex size-[30px] shrink-0 items-center justify-center rounded-lg bg-brand text-[11px] font-bold text-brand-foreground">
            {workspace.initials}
          </span>
          <span className="flex min-w-px flex-1 flex-col gap-0.5">
            <span className="text-[13px] font-semibold tracking-[-0.26px] text-foreground">
              {workspace.name}
            </span>
            <span className="text-[10px] tracking-[-0.2px] text-muted-light">
              {workspace.kind}
            </span>
          </span>
          <ChevronDownIcon className="size-4 shrink-0 text-muted-light" />
        </Link>

        <nav aria-label="Main menu" className="flex flex-col gap-1.5">
          <p className="text-[10px] font-bold tracking-[0.6px] text-muted-light">
            MENU
          </p>
          <ul className="flex flex-col gap-1 pt-1.5">
            {MENU.map(({ href, label, Icon }) => {
              const isActive = pathname === href;
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onClose}
                    aria-current={isActive ? "page" : undefined}
                    className={`flex items-center gap-3.5 rounded-[10px] px-3.5 py-[13px] text-[15px] tracking-[-0.3px] ${
                      isActive
                        ? "bg-brand font-semibold text-brand-foreground"
                        : "font-medium text-muted"
                    }`}
                  >
                    <Icon className="size-5 shrink-0" />
                    <span className="min-w-px flex-1">{label}</span>
                    {href === "/notifications" && unreadCount > 0 && (
                      <span className="flex size-[22px] shrink-0 items-center justify-center rounded-full bg-danger text-[11px] font-bold text-danger-foreground">
                        {unreadCount}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      <div className="flex flex-col gap-3">
        <span className="h-px w-full bg-border" />

        {user && (
          <div className="flex items-center gap-3 rounded-[10px] bg-canvas p-3">
            <span className="flex size-[38px] shrink-0 items-center justify-center rounded-full bg-brand-subtle text-[12px] font-bold text-brand">
              {user.initials}
            </span>
            <span className="flex min-w-px flex-1 flex-col gap-0.5">
              <span className="text-[13px] font-semibold tracking-[-0.26px] text-foreground">
                {user.name}
              </span>
              <span className="text-[11px] tracking-[-0.22px] text-muted-light">
                {user.department}
              </span>
            </span>
          </div>
        )}

        <Link
          href="/login"
          className="flex items-center gap-3 rounded-[10px] px-3.5 py-3 text-[15px] font-medium tracking-[-0.3px] text-muted"
        >
          <SignOutIcon className="size-[19px] shrink-0" />
          Sign out
        </Link>
      </div>
    </aside>
  );
}
