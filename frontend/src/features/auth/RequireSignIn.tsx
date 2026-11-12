"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { COGNITO_CLIENT_ID } from "@/lib/config";

import { isSignedIn } from "./session";

/**
 * Shows its children only to a signed-in user; anyone else goes to /login
 * (CLOUDAPPG5-122).
 *
 * The session is in localStorage, which only the browser has, so the check
 * runs after the first render. Until it passes nothing is shown: the pages
 * inside never start API calls without a token, and nothing private flashes.
 *
 * Without NEXT_PUBLIC_COGNITO_CLIENT_ID (the local demo) everyone is let in.
 *
 * This guards what the screen shows. The real protection is the backend,
 * which answers 401 to any request without a valid token.
 */
export default function RequireSignIn({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(!COGNITO_CLIENT_ID);

  useEffect(() => {
    if (!COGNITO_CLIENT_ID) return;
    if (isSignedIn()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reading browser storage once
      setAllowed(true);
    } else {
      router.replace("/login");
    }
  }, [router]);

  return allowed ? children : null;
}
