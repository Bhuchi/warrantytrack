"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { signOut, signedInUser } from "@/features/auth/session";
import { initialsOf } from "@/features/workspace/workspaces";

interface AppTopBarProps {
  /** Shown when nobody is signed in with Cognito (the local demo). */
  email: string;
  /** Two-letter avatar initials for the same case. */
  initials: string;
}

/**
 * White top bar for signed-in screens — Figma D03 (node 3344:3).
 *
 * Shows the signed-in user from the session (CLOUDAPPG5-122). The session is
 * in localStorage, which only exists in the browser, so it is read after the
 * first render; until then, and in the demo without Cognito, the props show.
 */
export default function AppTopBar({ email, initials }: AppTopBarProps) {
  const router = useRouter();
  const [user, setUser] = useState<{ email: string; initials: string } | null>(null);

  useEffect(() => {
    const signedIn = signedInUser();
    if (!signedIn) return;
    // Reading browser storage is a one-off sync with an outside system, which
    // is exactly what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUser({
      email: signedIn.email,
      initials: initialsOf(signedIn.name ?? signedIn.email),
    });
  }, []);

  function handleSignOut() {
    signOut();
    router.push("/login");
  }

  return (
    <header className="flex h-20 items-center justify-between bg-surface px-12">
      <Link href="/" className="flex items-center gap-3">
        <Image src="/warranty-logo-blue.svg" alt="" width={36} height={36} />
        <span className="text-[22px] font-bold text-brand">WarrantyTrack</span>
      </Link>

      <div className="flex items-center gap-2.5">
        <span className="text-[14px] tracking-[-0.28px] text-muted">
          {user?.email ?? email}
        </span>
        <span className="flex size-9 items-center justify-center rounded-full bg-brand-subtle text-[13px] font-bold text-brand">
          {user?.initials ?? initials}
        </span>
        <button
          type="button"
          onClick={handleSignOut}
          className="text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
