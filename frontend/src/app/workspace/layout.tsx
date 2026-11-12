import type { ReactNode } from "react";

import RequireSignIn from "@/features/auth/RequireSignIn";

/** Workspace selection is for signed-in users only (CLOUDAPPG5-122). */
export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return <RequireSignIn>{children}</RequireSignIn>;
}
