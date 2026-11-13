import type { Metadata } from "next";

import SettingsTeam from "@/features/settings/SettingsTeam";
import { getCurrentWorkspace } from "@/features/workspace/currentWorkspace";

export const metadata: Metadata = {
  title: "Settings: Team",
};

/** Settings → Team (CLOUDAPPG5-141). */
export default async function SettingsTeamPage() {
  const { kind } = await getCurrentWorkspace();
  return <SettingsTeam isOrganization={kind === "organization"} />;
}
