"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";
import { useToast } from "@/components/ToastProvider";
import { getMembers, inviteMember, isValidEmail, type InviteRole } from "@/features/workspace/members";
import { canManageAssets, useWorkspaceRole } from "@/features/workspace/WorkspaceRole";
import { selectedWorkspaceId } from "@/features/workspace/workspaces";
import type { MembershipRole, WorkspaceMember } from "@/types";

import SettingsTabs from "./SettingsTabs";

const ROLE_LABELS: Record<MembershipRole, string> = {
  owner: "Owner",
  admin: "Admin",
  employee: "Employee",
};

/** One white card, the same look as the cards on the Notifications tab. */
function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex w-full flex-col gap-3 rounded-[14px] border border-border bg-surface px-[18px] py-[14px]">
      <h2 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">{title}</h2>
      {children}
    </section>
  );
}

/** A grey note, for the states where there is nothing to manage. */
function Note({ children }: { children: ReactNode }) {
  return <p className="text-sm leading-5 text-muted">{children}</p>;
}

function MemberRow({ member }: { member: WorkspaceMember }) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-foreground">{member.display_name ?? member.email}</p>
        {member.display_name && <p className="truncate text-xs text-muted">{member.email}</p>}
      </div>
      {member.status === "invited" && (
        <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
          Invited
        </span>
      )}
      <span className="shrink-0 rounded-full bg-brand-subtle px-2.5 py-1 text-[11px] font-semibold text-brand">
        {ROLE_LABELS[member.role]}
      </span>
    </li>
  );
}

/**
 * Settings → Team (CLOUDAPPG5-141): who is in this organization, and a form
 * to invite someone by email. The invited person sees the invite on
 * Workspace Selection the next time they sign in with that email.
 */
export default function SettingsTeam({ isOrganization }: { isOrganization: boolean }) {
  const role = useWorkspaceRole();
  const showToast = useToast();
  const canManage = isOrganization && canManageAssets(role);

  const [members, setMembers] = useState<WorkspaceMember[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<InviteRole>("employee");
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Load the team once we know the user may see it.
  useEffect(() => {
    if (!canManage) return;
    let ignore = false;
    getMembers(selectedWorkspaceId() ?? "")
      .then((result) => {
        if (!ignore) setMembers(result);
      })
      .catch((error: unknown) => {
        if (!ignore) setLoadError(error instanceof Error ? error.message : "Couldn't load the team.");
      });
    return () => {
      ignore = true;
    };
  }, [canManage]);

  async function sendInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); // Stop the browser reloading the page on submit.
    if (!isValidEmail(email)) {
      setFormError("Enter an email address like name@company.com.");
      return;
    }
    setSending(true);
    setFormError(null);
    try {
      const invited = await inviteMember(selectedWorkspaceId() ?? "", email, inviteRole);
      setMembers((current) => [...(current ?? []), invited]);
      setEmail("");
      showToast({
        tone: "success",
        title: "Invite sent",
        message: `${invited.email} can accept it on Workspace Selection after signing in.`,
      });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Couldn't send the invite.");
    } finally {
      setSending(false);
    }
  }

  let body: ReactNode;
  if (!isOrganization) {
    body = (
      <Card title="Team">
        <Note>
          Teams are for organization workspaces. Your Personal workspace is only for you.{" "}
          <Link href="/workspace" className="font-semibold text-brand underline">
            Create or switch to an organization
          </Link>
          .
        </Note>
      </Card>
    );
  } else if (role === null) {
    body = (
      <Card title="Team">
        <Note>Loading…</Note>
      </Card>
    );
  } else if (!canManage) {
    body = (
      <Card title="Team">
        <Note>Only owners and admins can manage the team. Ask one of them to invite people.</Note>
      </Card>
    );
  } else {
    body = (
      <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-2 md:gap-5">
        <Card title="Invite someone">
          <form onSubmit={sendInvite} noValidate className="flex flex-col gap-4">
            <TextField
              id="invite-email"
              label="Email"
              iconSrc="/icons/mail.svg"
              type="email"
              autoComplete="off"
              placeholder="name@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={formError ? true : undefined}
              aria-describedby={formError ? "invite-error" : undefined}
            />
            <div className="flex flex-col gap-2">
              <label htmlFor="invite-role" className="text-[13px] font-semibold tracking-[-0.26px] text-foreground">
                Role
              </label>
              <select
                id="invite-role"
                value={inviteRole}
                onChange={(event) => setInviteRole(event.target.value as InviteRole)}
                className="h-[54px] rounded-[10px] border border-border bg-surface px-4 text-[15px] outline-none focus:border-brand md:h-[52px] md:rounded-lg"
              >
                <option value="employee">Employee: sees only their own assets</option>
                <option value="admin">Admin: sees all assets and manages the team</option>
              </select>
            </div>
            {formError && (
              <p id="invite-error" role="alert" className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
                {formError}
              </p>
            )}
            <Button type="submit" disabled={sending}>
              {sending ? "Sending…" : "Send invite"}
            </Button>
            <p className="text-[11px] leading-4 text-muted-light">
              They join after they sign in with this email and accept the invite on Workspace Selection.
            </p>
          </form>
        </Card>

        <Card title={members ? `Members (${members.length})` : "Members"}>
          {loadError ? (
            <p role="alert" className="text-sm text-red-700">
              {loadError}
            </p>
          ) : members === null ? (
            <Note>Loading…</Note>
          ) : (
            <ul className="-my-2.5 divide-y divide-border">
              {members.map((member) => (
                <MemberRow key={member.email} member={member} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-[14px] md:gap-5 md:px-8 md:pt-8 lg:px-12">
        <div className="flex flex-col gap-1">
          <h1 className="text-[22px] font-bold leading-[27px] tracking-[-0.44px] text-brand">Settings</h1>
          <p className="text-xs leading-[17px] tracking-[-0.24px] text-muted">
            Invite people to this organization and see who has access.
          </p>
        </div>
        <SettingsTabs active="team" />
        {body}
      </main>
    </div>
  );
}
