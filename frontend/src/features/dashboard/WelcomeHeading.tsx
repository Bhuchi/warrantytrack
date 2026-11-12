"use client";

import { useEffect, useState } from "react";

import { signedInUser } from "@/features/auth/session";
import { COGNITO_CLIENT_ID } from "@/lib/config";

/**
 * "Welcome back, <first name>" on the Dashboard (CLOUDAPPG5-123).
 *
 * The name is in the session, which only the browser has, so it is read after
 * the first render. Until then, or with no name, it just says "Welcome back".
 * Without Cognito (the local demo) it keeps the Figma placeholder name.
 */
export default function WelcomeHeading() {
  const [firstName, setFirstName] = useState<string | null>(COGNITO_CLIENT_ID ? null : "Chaiyapat");

  useEffect(() => {
    if (!COGNITO_CLIENT_ID) return;
    const name = signedInUser()?.name?.trim();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading browser storage once
    if (name) setFirstName(name.split(/\s+/)[0]);
  }, []);

  return (
    <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand md:text-[30px] md:tracking-[-0.6px]">
      {firstName ? `Welcome back, ${firstName}` : "Welcome back"}
    </h1>
  );
}
