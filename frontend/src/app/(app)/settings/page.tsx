import type { Metadata } from "next";

import SettingsNotifications from "@/features/settings/SettingsNotifications";

export const metadata: Metadata = {
  title: "Settings — Notifications",
};

export default function SettingsPage() {
  return <SettingsNotifications />;
}
