"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import Button from "@/components/Button";
import Modal from "@/components/Modal";
import TextField from "@/components/TextField";
import { useToast } from "@/components/ToastProvider";
import { signedInUser } from "@/features/auth/session";
import {
  cancelInvite,
  getMembers,
  inviteMember,
  isValidEmail,
  leaveOrganization,
  removeMember,
  type InviteRole,
} from "@/features/workspace/members";
import { canManageAssets, useWorkspaceRole } from "@/features/workspace/WorkspaceRole";
import { rememberWorkspace, selectedWorkspaceId } from "@/features/workspace/workspaces";
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

/** What the confirm dialog is about. `null` means the dialog is closed. */
type PendingAction =
  | { kind: "cancel"; member: WorkspaceMember }
  | { kind: "remove"; member: WorkspaceMember }
  | { kind: "leave" };

function nameOf(member: WorkspaceMember): string {
  return member.display_name ?? member.email;
}

function MemberRow({
  member,
  action,
}: {
  member: WorkspaceMember;
  /** The one button this row offers, if any (Remove or Cancel invite). */
  action?: { label: string; onClick: () => void };
}) {
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
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          aria-label={`${action.label}: ${nameOf(member)}`}
          className="-my-1.5 shrink-0 rounded-md px-2 py-1.5 text-xs font-semibold text-danger hover:bg-red-50"
        >
          {action.label}
        </button>
      )}
    </li>
  );
}

/**
 * Settings → Team (CLOUDAPPG5-141): who is in this organization, a form to
 * invite someone by email, and the actions that undo membership: cancel an
 * invite, remove a member, leave (GitHub #80). The invited person sees the
 * invite on Workspace Selection the next time they sign in with that email.
 */
export default function SettingsTeam({
  isOrganization,
  organizationName,
}: {
  isOrganization: boolean;
  organizationName: string;
}) {
  const role = useWorkspaceRole();
  const router = useRouter();
  const showToast = useToast();
  const canManage = isOrganization && canManageAssets(role);
  // The owner can't leave: an organization must always keep its owner.
  const canLeave = isOrganization && (role === "admin" || role === "employee");

  // Your own email, so your row never offers "Remove" (use Leave instead).
  const [myEmail, setMyEmail] = useState<string | null>(null);
  useEffect(() => {
    // Reading browser storage is a one-off sync with an outside system.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMyEmail(signedInUser()?.email.toLowerCase() ?? null);
  }, []);

  const [pending, setPending] = useState<PendingAction | null>(null);
  const [working, setWorking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

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

  function closeDialog() {
    if (working) return; // Don't hide the dialog halfway through a request.
    setPending(null);
    setActionError(null);
  }

  /** Runs whatever the open dialog is about, then updates the screen. */
  async function confirmAction() {
    if (!pending) return;
    const workspaceId = selectedWorkspaceId() ?? "";
    setWorking(true);
    setActionError(null);
    try {
      if (pending.kind === "leave") {
        await leaveOrganization(workspaceId);
        rememberWorkspace("personal"); // This organization is no longer yours to open.
        showToast({ tone: "success", title: `You left ${organizationName}` });
        router.push("/workspace");
        return;
      }
      const { member } = pending;
      if (pending.kind === "cancel") {
        await cancelInvite(workspaceId, member.email);
        showToast({ tone: "success", title: "Invite cancelled", message: `${member.email} won't see it any more.` });
      } else {
        await removeMember(workspaceId, member.user_id ?? "");
        showToast({ tone: "success", title: "Member removed", message: `${nameOf(member)} no longer has access.` });
      }
      setMembers((current) => (current ?? []).filter((item) => item.email !== member.email));
      setPending(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Something went wrong. Please try again.");
    } finally {
      setWorking(false);
    }
  }

  /** Which button a row gets: none for the owner or yourself. */
  function actionFor(member: WorkspaceMember) {
    if (member.status === "invited") {
      return { label: "Cancel invite", onClick: () => setPending({ kind: "cancel", member }) };
    }
    if (member.role === "owner" || member.email.toLowerCase() === myEmail || !member.user_id) return undefined;
    return { label: "Remove", onClick: () => setPending({ kind: "remove", member }) };
  }

  // The dialog's words depend on which action is pending.
  const dialog =
    pending?.kind === "cancel"
      ? {
          title: "Cancel this invite?",
          text: `${pending.member.email} won't see the invite on Workspace Selection any more. You can invite them again later.`,
          confirm: "Cancel invite",
          dismiss: "Keep invite",
        }
      : pending?.kind === "remove"
        ? {
            title: `Remove ${nameOf(pending.member)}?`,
            text: `They lose access to ${organizationName} straight away. Assets assigned to them become unassigned. You can invite them again later.`,
            confirm: "Remove",
            dismiss: "Cancel",
          }
        : {
            title: `Leave ${organizationName}?`,
            text: `You lose access to its assets straight away. An owner or admin can invite you again.`,
            confirm: "Leave",
            dismiss: "Cancel",
          };

  const leaveCard = canLeave ? (
    <Card title={`Leave ${organizationName}`}>
      <Note>You will lose access to this organization and its assets. Your Personal workspace is not affected.</Note>
      <button
        type="button"
        onClick={() => setPending({ kind: "leave" })}
        className="flex h-[48px] w-full items-center justify-center rounded-[10px] border border-danger bg-surface text-[15px] font-bold text-danger md:w-fit md:px-6"
      >
        Leave organization
      </button>
    </Card>
  ) : null;

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
                <MemberRow key={member.email} member={member} action={actionFor(member)} />
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
        {leaveCard}
      </main>

      <Modal
        open={pending !== null}
        onClose={closeDialog}
        title={dialog.title}
        actions={
          <>
            <Button variant="secondary" onClick={closeDialog} disabled={working}>
              {dialog.dismiss}
            </Button>
            <Button variant="danger" onClick={confirmAction} disabled={working}>
              {working ? "Working…" : dialog.confirm}
            </Button>
          </>
        }
      >
        <p>{dialog.text}</p>
        {actionError && (
          <p role="alert" className="mt-3 rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {actionError}
          </p>
        )}
      </Modal>
    </div>
  );
}
