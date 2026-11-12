import type { ReactNode } from "react";

import ToastProvider from "@/components/ToastProvider";
import RequireSignIn from "@/features/auth/RequireSignIn";
import { getCurrentWorkspace } from "@/features/workspace/currentWorkspace";
import SignedInShell from "@/features/workspace/SignedInShell";

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
 * RequireSignIn sends anyone who is not signed in to /login (CLOUDAPPG5-122).
 *
 * SignedInShell swaps the cookie-based placeholders for the real workspace,
 * user and unread count from GET /me and GET /notifications (CLOUDAPPG5-123).
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const { workspace, user, unreadCount } = await getCurrentWorkspace();

  return (
    <RequireSignIn>
      <ToastProvider>
        <SignedInShell placeholder={{ workspace, user, unreadCount }}>
          {children}
        </SignedInShell>
      </ToastProvider>
    </RequireSignIn>
  );
}
