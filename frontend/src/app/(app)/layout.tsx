import type { ReactNode } from "react";

import AppShell from "@/components/AppShell";
import ToastProvider from "@/components/ToastProvider";
import { getCurrentWorkspace } from "@/features/workspace/currentWorkspace";
import AuthenticatedAppShell from "@/features/auth/AuthenticatedAppShell";
import { AUTH_REQUIRED } from "@/lib/config";

/**
 * Wraps every signed-in screen with the navigation panel and mobile top bar,
 * and the ToastProvider, so a toast survives moving between these pages.
 * Marketing pages live in (marketing) and auth pages in (auth); neither gets
 * this chrome.
 *
 * The nav panel shows the workspace chosen on /workspace, read from the
 * "workspace" cookie. Reading a cookie makes these pages render on every
 * request instead of once at build time.
 *
 * TODO (FE-05, CLOUDAPPG5-123): the names, user and unread count are still the
 * Figma placeholders; read them from GET /me once /workspaces exists.
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  if (AUTH_REQUIRED) return <AuthenticatedAppShell>{children}</AuthenticatedAppShell>;
  const { workspace, user, unreadCount } = await getCurrentWorkspace();

  return (
    <ToastProvider>
      <AppShell workspace={workspace} user={user} unreadCount={unreadCount}>
        {children}
      </AppShell>
    </ToastProvider>
  );
}
