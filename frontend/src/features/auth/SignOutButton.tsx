"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { signOutSession } from "./cognito";

export default function SignOutButton({ className, children }: {
  className: string;
  children?: ReactNode;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  async function leave() {
    setBusy(true);
    setError(false);
    try {
      await signOutSession();
      router.replace("/login");
      router.refresh();
    } catch {
      setError(true);
      setBusy(false);
    }
  }
  return <div>
    <button type="button" onClick={leave} disabled={busy} className={className}>
      {children}Sign out
    </button>
    {error && <span role="alert" className="text-[11px] text-danger">Sign out failed. Try again.</span>}
  </div>;
}
