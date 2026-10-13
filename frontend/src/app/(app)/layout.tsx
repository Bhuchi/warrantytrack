import type { ReactNode } from "react";

import AppShell from "@/components/AppShell";

/**
 * Wraps every signed-in screen with the navigation panel and mobile top bar.
 * Marketing pages live in (marketing) and auth pages in (auth); neither gets
 * this chrome.
 *
 * TODO: workspace, user and unread count are the Figma placeholders. Read them
 * from the session and the API once auth and /workspaces exist (FE-04, FE-05).
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AppShell
      workspace={{
        name: "SIIT Organization",
        kind: "Organization workspace",
        initials: "SI",
      }}
      user={{
        name: "Chaiyapat A.",
        department: "IT Department",
        initials: "CA",
      }}
      unreadCount={3}
    >
      {children}
    </AppShell>
  );
}
