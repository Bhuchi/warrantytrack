"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { Invite, MeResponse, Membership } from "@/types";
import { api } from "@/lib/api";
import { COGNITO_CLIENT_ID } from "@/lib/config";

import CreateOrganizationModal from "./CreateOrganizationModal";
import CreateWorkspaceCard from "./CreateWorkspaceCard";
import InviteCard from "./InviteCard";
import { acceptInvite, declineInvite, getInvites } from "./invites";
import WorkspaceCard from "./WorkspaceCard";
import { rememberWorkspace, selectedWorkspaceId } from "./workspaces";
import { OrganizationIcon, PersonalIcon } from "./WorkspaceIcons";

/**
 * "use client" marks this as a Client Component: it runs in the browser, so it
 * can hold state and respond to clicks. Everything it imports becomes client
 * code too, so keep the boundary as low in the tree as possible.
 *
 * Desktop (D03) gives each card its own Continue button. Mobile (M03) drops
 * those for one shared button at the bottom, which needs to know the current
 * selection — so it lives here, where the state is.
 *
 * Continue saves the chosen workspace UUID and display metadata in cookies,
 * so later API calls send X-Workspace-Id and the nav survives a refresh.
 *
 * A new user (`isNewUser`, CLOUDAPPG5-132) has only their personal
 * workspace, with nothing in it yet, plus a card to create an organization.
 *
 * Pending organization invites (CLOUDAPPG5-133, issue #37) show above the
 * workspaces. Accepting one adds that organization as a workspace card and
 * selects it; declining removes the invite. Figma 3641:18 / 3642:187.
 *
 * With Cognito configured, GET /me supplies every real membership. The
 * placeholder cards and invite demo remain for local UI work without auth.
 *
 * TODO: the counts below are the placeholder values from Figma. Replace with
 * real data from lib/api once the workspaces endpoint exists.
 */

const WORKSPACES = [
  {
    id: "personal",
    title: "Personal Workspace",
    description:
      "Manage your own devices, receipts and warranties in a private space only you can see.",
    descriptionShort: "Private space only you can see.",
    href: "/dashboard",
    stats: [
      { value: "12", label: "Assets" },
      { value: "1", label: "Expiring soon" },
    ],
  },
  {
    id: "organization",
    title: "Organization Workspace",
    description:
      "Track assets and warranties across departments, with shared visibility for your whole team.",
    descriptionShort: "Shared across your whole team.",
    href: "/dashboard",
    stats: [
      { value: "128", label: "Assets" },
      { value: "5", label: "Departments" },
    ],
  },
] as const;

/** A new user's personal workspace is empty (Figma 3640:18). */
const NEW_USER_STATS = [
  { value: "0", label: "Assets" },
  { value: "0", label: "Expiring soon" },
];

export default function WorkspaceSelector({ isNewUser = false }: { isNewUser?: boolean }) {
  const router = useRouter();

  // Figma shows the organization card selected by default; a new user only
  // has their personal workspace, so that one starts selected.
  const [selected, setSelected] = useState<string>(isNewUser ? "personal" : "organization");
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(COGNITO_CLIENT_ID));
  const [creating, setCreating] = useState(false);

  const [invites, setInvites] = useState<Invite[]>([]);
  /** The organization joined by accepting an invite on this page, if any. */
  const [joinedName, setJoinedName] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  useEffect(() => {
    if (!COGNITO_CLIENT_ID) return;
    let ignore = false;
    api.get<MeResponse>("/me")
      .then(({ memberships: result }) => {
        if (ignore) return;
        setMemberships(result);
        const saved = selectedWorkspaceId();
        setSelected(result.find((item) => item.workspace.id === saved)?.workspace.id
          ?? result[0]?.workspace.id ?? "");
      })
      .catch(() => {
        if (!ignore) setLoadError("Could not load your workspaces. Please sign in and try again.");
      })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  // Load pending invites once, after the first render. If that fails the page
  // still works; the user just doesn't see invites until they reload.
  useEffect(() => {
    if (COGNITO_CLIENT_ID) return;
    let ignore = false;
    getInvites()
      .then((result) => {
        if (!ignore) setInvites(result);
      })
      .catch(() => {});
    return () => {
      ignore = true;
    };
  }, []);

  /** Takes an invite off the screen once it has been accepted or declined. */
  function removeInvite(invite: Invite) {
    setInvites((list) =>
      list.filter((item) => item.workspace.id !== invite.workspace.id),
    );
  }

  async function handleAccept(invite: Invite) {
    setInviteError(null);
    try {
      const membership = await acceptInvite(invite.workspace.id);
      removeInvite(invite);
      setJoinedName(membership.workspace.name);
      setSelected("organization");
    } catch {
      setInviteError(
        `Couldn't accept the invite to ${invite.workspace.name}. Please try again.`,
      );
    }
  }

  async function handleDecline(invite: Invite) {
    setInviteError(null);
    try {
      await declineInvite(invite.workspace.id);
      removeInvite(invite);
    } catch {
      setInviteError(
        `Couldn't decline the invite to ${invite.workspace.name}. Please try again.`,
      );
    }
  }

  // A new user has no organization, unless they just accepted an invite.
  const showOrganization = !isNewUser || joinedName !== null;
  const workspaces = COGNITO_CLIENT_ID
    ? memberships.map((membership) => {
        const workspace = membership.workspace;
        const template = WORKSPACES.find((item) => item.id === workspace.type)!;
        return { ...template, id: workspace.id, kind: workspace.type,
          title: workspace.name, stats: [] };
      })
    : (showOrganization ? WORKSPACES : WORKSPACES.filter((item) => item.id === "personal"))
        .map((item) => ({ ...item, kind: item.id }));

  /** The organization's name goes in the cookie, so the nav panel shows it. */
  const remember = (id: string) => {
    const chosen = workspaces.find((item) => item.id === id);
    if (chosen) rememberWorkspace(chosen.kind, COGNITO_CLIENT_ID
      ? chosen.title : chosen.kind === "organization" ? (joinedName ?? undefined) : undefined,
      COGNITO_CLIENT_ID ? chosen.id : undefined);
  };
  const selectedWorkspace =
    workspaces.find((workspace) => workspace.id === selected) ?? workspaces[0];

  return (
    <div className="flex w-full flex-col gap-5 md:items-center md:gap-11">
      {loading && <p role="status">Loading your workspaces…</p>}
      {loadError && <p role="alert" className="text-danger">{loadError}</p>}
      {(invites.length > 0 || inviteError) && (
        <div className="flex w-full flex-col gap-3">
          {invites.map((invite) => (
            <InviteCard
              key={invite.workspace.id}
              invite={invite}
              onAccept={() => handleAccept(invite)}
              onDecline={() => handleDecline(invite)}
            />
          ))}
          {inviteError && (
            <p
              role="alert"
              className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700"
            >
              {inviteError}
            </p>
          )}
        </div>
      )}

      <div className="flex w-full flex-col gap-5 md:flex-row md:items-start md:gap-8">
        {workspaces.map((workspace) => (
          <WorkspaceCard
            key={workspace.id}
            title={
              workspace.kind === "organization" && joinedName && !COGNITO_CLIENT_ID
                ? joinedName
                : workspace.title
            }
            description={workspace.description}
            descriptionShort={workspace.descriptionShort}
            href={workspace.href}
            stats={
              !COGNITO_CLIENT_ID && isNewUser && workspace.kind === "personal"
                ? NEW_USER_STATS
                : [...workspace.stats]
            }
            icon={
              workspace.kind === "personal" ? (
                <PersonalIcon className="size-6 md:size-[26px]" />
              ) : (
                <OrganizationIcon className="size-6 md:size-[26px]" />
              )
            }
            selected={workspace.id === selected}
            onSelect={() => setSelected(workspace.id)}
            onContinue={() => remember(workspace.id)}
          />
        ))}

        {(COGNITO_CLIENT_ID || isNewUser) && <CreateWorkspaceCard onCreate={() => setCreating(true)} />}
      </div>

      {/* While an invite is showing, "ask its admin to invite you" makes no sense. */}
      {invites.length === 0 && (
        <p className="flex w-full items-center gap-2.5 rounded-[10px] bg-brand-subtle px-4 py-3.5 text-[13px] leading-[19px] tracking-[-0.26px] text-brand md:w-auto md:rounded-lg md:py-3.5 md:pr-5 md:pl-[18px] md:text-[14px] md:tracking-[-0.28px]">
          <Image
            src="/icons/info.svg"
            alt=""
            width={18}
            height={18}
            className="shrink-0"
          />
          {isNewUser
            ? "Joining a company? Ask its admin to invite you."
            : "You can switch workspaces anytime from the navigation menu."}
        </p>
      )}

      {selectedWorkspace && <Link
        href={selectedWorkspace.href}
        onClick={() => remember(selected)}
        className="flex h-14 w-full items-center justify-center rounded-[10px] bg-brand text-[17px] font-bold tracking-[-0.34px] text-brand-foreground md:hidden"
      >
        Continue
      </Link>}

      <CreateOrganizationModal
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(workspace) => {
          // The new organization becomes the chosen workspace, then straight in.
          rememberWorkspace("organization", workspace.name,
            COGNITO_CLIENT_ID ? workspace.id : undefined);
          router.push("/dashboard");
        }}
      />
    </div>
  );
}
