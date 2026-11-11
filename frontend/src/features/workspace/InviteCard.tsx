"use client";

import { useState } from "react";

import type { Invite } from "@/types";

import { initialsOf } from "./workspaces";

const ROLE_LABELS: Record<Invite["role"], string> = {
  admin: "Admin",
  employee: "Employee",
};

/** "10 Nov 2026" */
function formatDay(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

interface InviteCardProps {
  invite: Invite;
  /** What Accept does. The card shows "Accepting…" until it finishes. */
  onAccept: () => Promise<void>;
  /** What Decline does. The card shows "Declining…" until it finishes. */
  onDecline: () => Promise<void>;
}

/**
 * One pending organization invite on Workspace Selection (CLOUDAPPG5-133).
 * Figma: desktop 3641:18 (one row), mobile 3642:187 (stacked, two equal buttons).
 *
 * The parent decides what Accept and Decline do, and shows any error; this
 * card only knows which button is busy.
 */
export default function InviteCard({ invite, onAccept, onDecline }: InviteCardProps) {
  const [busy, setBusy] = useState<"accept" | "decline" | null>(null);

  async function run(action: "accept" | "decline", handler: () => Promise<void>) {
    setBusy(action);
    try {
      await handler();
    } finally {
      // Runs whether it worked or not, so a failed call frees the buttons again.
      setBusy(null);
    }
  }

  const { workspace } = invite;
  const buttonClasses =
    "flex h-12 flex-1 items-center justify-center rounded-lg text-[15px] font-bold tracking-[-0.3px] disabled:cursor-not-allowed disabled:opacity-50 md:h-11 md:flex-none md:px-[22px]";

  return (
    <section
      aria-label={`Invitation to ${workspace.name}`}
      className="flex w-full flex-col gap-4 rounded-2xl border-[1.5px] border-brand bg-surface p-5 md:flex-row md:items-center md:gap-[18px] md:px-7 md:py-[22px]"
    >
      <div className="flex items-center gap-3.5 md:flex-1 md:gap-[18px]">
        <span className="flex size-[50px] shrink-0 items-center justify-center rounded-[14px] bg-brand-subtle text-[16px] font-bold text-brand md:size-[52px] md:text-[17px]">
          {initialsOf(workspace.name)}
        </span>
        <div className="flex min-w-0 flex-col gap-1 md:gap-1.5">
          {/* Desktop only, as in Figma 3641:18. */}
          <span className="hidden w-fit rounded-full bg-brand-subtle px-[9px] py-1 text-[11px] font-semibold text-brand md:inline-flex">
            Invitation
          </span>
          <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground md:text-[19px] md:tracking-[-0.38px]">
            {invite.invited_by} invited you to {workspace.name}
          </h2>
          <p className="text-[13px] tracking-[-0.26px] text-muted md:text-[14px] md:tracking-[-0.28px]">
            Join as {ROLE_LABELS[invite.role]} · Invited {formatDay(invite.invited_at)}
          </p>
        </div>
      </div>

      <div className="flex gap-2.5 md:shrink-0">
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => run("decline", onDecline)}
          className={`${buttonClasses} border border-border bg-surface text-foreground`}
        >
          {busy === "decline" ? "Declining…" : "Decline"}
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => run("accept", onAccept)}
          className={`${buttonClasses} bg-brand text-brand-foreground`}
        >
          {busy === "accept" ? "Accepting…" : "Accept"}
        </button>
      </div>
    </section>
  );
}
