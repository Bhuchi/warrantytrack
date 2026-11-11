"use client";

import { useSignedInName } from "@/features/auth/SignedInContext";
import { AUTH_REQUIRED } from "@/lib/config";

export default function DashboardGreeting() {
  const name = useSignedInName();
  return <>Welcome back, {AUTH_REQUIRED ? name?.split(" ")[0] ?? "" : "Chaiyapat"}</>;
}
