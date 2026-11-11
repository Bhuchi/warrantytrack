"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import AppShell from "@/components/AppShell";
import ErrorState from "@/components/ErrorState";
import type { NavUser, NavWorkspace } from "@/components/NavPanel";
import { api } from "@/lib/api";
import { COGNITO_CLIENT_ID } from "@/lib/config";
import type { MeResponse, MembershipRole } from "@/types";
import type { NotificationListResponse } from "@/types/notifications";

import { initialsOf, selectedWorkspaceId } from "./workspaces";

interface ShellData {
  workspace: NavWorkspace;
  user: NavUser | null;
  unreadCount: number;
}

const ROLE_LABELS: Record<MembershipRole, string> = {
  owner: "Owner",
  admin: "Administrator",
  employee: "Employee",
};

/**
 * The navigation shell with the real workspace, user and unread count
 * (FE-05, CLOUDAPPG5-123), loaded in the browser because the token lives there.
 *
 * - The unread badge comes from GET /notifications, also in the local demo.
 * - With Cognito, the workspace and user come from GET /me. The workspace is
 *   the one chosen on /workspace (the workspace_id cookie); if it is not one
 *   of the user's memberships any more, they are sent back to choose again.
 * - Without Cognito, `placeholder` (the Figma values) shows straight away.
 *
 * The user card shows the role where Figma shows a department: /me has no
 * department. Personal workspaces have no user card, as in Figma M10.
 */
export default function SignedInShell({
  placeholder,
  children,
}: {
  placeholder: ShellData;
  children: ReactNode;
}) {
  const router = useRouter();
  const [data, setData] = useState<ShellData | null>(COGNITO_CLIENT_ID ? null : placeholder);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function load() {
      const unread = await api
        .get<NotificationListResponse>("/notifications")
        .then((list) => list.unread)
        .catch(() => null);

      if (!COGNITO_CLIENT_ID) {
        if (!ignore && unread !== null) {
          setData((current) => current && { ...current, unreadCount: unread });
        }
        return;
      }

      const me = await api.get<MeResponse>("/me");
      // The user may have left this page while /me was loading. A late answer
      // must not redirect them or update a screen that is gone.
      if (ignore) return;

      const membership = me.memberships.find(
        ({ workspace }) => workspace.id === selectedWorkspaceId(),
      );
      if (!membership) {
        router.replace("/workspace");
        return;
      }

      const { workspace, role } = membership;
      const userName = me.user.display_name || me.user.email;
      setData({
        workspace: {
          name: workspace.name,
          kind: workspace.type === "personal" ? "Personal workspace" : "Organization workspace",
          initials: initialsOf(workspace.name),
        },
        user:
          workspace.type === "personal"
            ? null
            : { name: userName, department: ROLE_LABELS[role], initials: initialsOf(userName) },
        unreadCount: unread ?? 0,
      });
    }

    load().catch(() => {
      if (!ignore) setFailed(true);
    });
    return () => {
      ignore = true;
    };
  }, [router, placeholder, attempt]);

  if (failed) {
    return (
      <main className="flex flex-1 items-center justify-center p-8">
        <ErrorState
          message="We could not load your workspace. Check your connection and try again."
          action={
            <button
              type="button"
              onClick={() => {
                setFailed(false);
                setAttempt((n) => n + 1);
              }}
              className="text-[14px] font-semibold text-brand underline"
            >
              Try again
            </button>
          }
        />
      </main>
    );
  }

  if (!data) {
    return (
      <main role="status" className="flex flex-1 items-center justify-center p-8 text-[14px] text-muted">
        Loading your workspace…
      </main>
    );
  }

  return (
    <AppShell workspace={data.workspace} user={data.user} unreadCount={data.unreadCount}>
      {children}
    </AppShell>
  );
}
