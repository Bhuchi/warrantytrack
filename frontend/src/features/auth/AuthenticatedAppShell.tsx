"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import AppShell from "@/components/AppShell";
import ToastProvider from "@/components/ToastProvider";
import { api } from "@/lib/api";
import type { MeResponse } from "@/types";
import type { NotificationListResponse } from "@/types/notifications";
import { clearWorkspace, initialsOf, selectedWorkspaceId } from "@/features/workspace/workspaces";
import { getIdToken } from "./cognito";
import { SignedInNameContext } from "./SignedInContext";

type ShellData = {
  workspace: { name: string; kind: string; initials: string };
  user: { name: string; department: string; initials: string };
  unreadCount: number;
};

export default function AuthenticatedAppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [data, setData] = useState<ShellData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        if (!await getIdToken()) {
          clearWorkspace();
          router.replace("/login");
          return;
        }
        const me = await api.get<MeResponse>("/me");
        const membership = me.memberships.find(({ workspace }) => workspace.id === selectedWorkspaceId());
        if (!membership) {
          clearWorkspace();
          router.replace("/workspace");
          return;
        }
        const displayName = me.user.display_name || me.user.email;
        const notifications = await api.get<NotificationListResponse>("/notifications").catch(() => null);
        if (active) setData({
          workspace: {
            name: membership.workspace.name,
            kind: membership.workspace.type === "personal" ? "Personal workspace" : "Organization workspace",
            initials: initialsOf(membership.workspace.name),
          },
          user: {
            name: displayName,
            department: membership.role === "owner" ? "Owner" :
              membership.role === "admin" ? "Administrator" : "Employee",
            initials: initialsOf(displayName),
          },
          unreadCount: notifications?.unread ?? 0,
        });
      } catch {
        if (active) setError("Could not load your account. Please try again.");
      }
    }
    void load();
    return () => { active = false; };
  }, [router]);

  if (error) return <main role="alert" className="p-8">{error}{" "}
    <button type="button" className="text-brand underline" onClick={() => window.location.reload()}>Retry</button>
  </main>;
  if (!data) return <main role="status" className="p-8">Loading your workspace…</main>;
  return <SignedInNameContext.Provider value={data.user.name}>
    <ToastProvider><AppShell {...data}>{children}</AppShell></ToastProvider>
  </SignedInNameContext.Provider>;
}
