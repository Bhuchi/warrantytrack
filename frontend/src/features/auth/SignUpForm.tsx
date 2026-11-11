"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";
import { AUTH_REQUIRED, COGNITO_ENABLED } from "@/lib/config";
import { authError, confirmEmail, resendConfirmationCode, signInWithEmail, signUpWithEmail } from "./cognito";

export default function SignUpForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!COGNITO_ENABLED) {
      if (AUTH_REQUIRED) setError("Cognito pool and client IDs are missing from this deployment.");
      else router.push("/workspace?new=1");
      return;
    }
    if (!confirming && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      if (!confirming) {
        const result = await signUpWithEmail(name, email, password);
        if (result.isSignUpComplete) {
          const session = await signInWithEmail(email, password, true);
          if (session.isSignedIn) router.replace("/workspace");
          else router.replace("/login");
        } else {
          setConfirming(true);
        }
      } else {
        await confirmEmail(email, code);
        const session = await signInWithEmail(email, password, true);
        if (session.isSignedIn) router.replace("/workspace");
        else router.replace("/login");
      }
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="flex w-full flex-col gap-[22px]" onSubmit={submit}>
      {confirming ? <>
        <p className="text-[14px] text-muted">Enter the confirmation code sent to {email}.</p>
        <TextField id="signup-code" label="Confirmation code" type="text" autoComplete="one-time-code"
          iconSrc="/icons/mail.svg" required value={code} onChange={(event) => setCode(event.target.value)} />
      </> : <>
        <TextField id="name" name="name" label="Full name" type="text" autoComplete="name"
          placeholder="Jane Doe" iconSrc="/icons/user.svg" required value={name}
          onChange={(event) => setName(event.target.value)} />
        <TextField id="signup-email" name="email" label="Email" type="email" autoComplete="email"
          placeholder="you@example.com" iconSrc="/icons/mail.svg" required value={email}
          onChange={(event) => setEmail(event.target.value)} />
        <TextField id="signup-password" name="password" label="Password" type="password"
          autoComplete="new-password" placeholder="At least 8 characters" iconSrc="/icons/lock.svg"
          required value={password} onChange={(event) => setPassword(event.target.value)} />
        <TextField id="confirm-password" name="confirmPassword" label="Confirm password" type="password"
          autoComplete="new-password" placeholder="Re-enter your password" iconSrc="/icons/lock.svg"
          required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
        <label htmlFor="terms" className="flex items-start gap-2.5 text-[14px] leading-5 tracking-[-0.28px] text-foreground">
          <span className="relative inline-flex size-5 shrink-0">
            <input id="terms" name="terms" type="checkbox" required
              className="peer size-5 appearance-none rounded-[5px] border border-border checked:border-brand checked:bg-brand" />
            <Image src="/icons/check-small.svg" alt="" width={13} height={13}
              className="pointer-events-none absolute inset-0 m-auto hidden peer-checked:block" />
          </span>
          <span>I agree to the <Link href="/terms" className="font-semibold text-brand">Terms</Link> and{" "}
            <Link href="/privacy" className="font-semibold text-brand">Privacy Policy</Link>.</span>
        </label>
      </>}
      {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
      {confirming && <button type="button" className="text-left text-[14px] font-semibold text-brand"
        onClick={() => void resendConfirmationCode(email).catch((cause) => setError(authError(cause)))}>
        Resend confirmation code
      </button>}
      <Button type="submit" disabled={busy}>
        {busy ? "Please wait…" : confirming ? "Confirm Account" : "Create Account"}
      </Button>
    </form>
  );
}
