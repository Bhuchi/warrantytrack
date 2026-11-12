"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";
import { COGNITO_CLIENT_ID } from "@/lib/config";

import { CognitoError, resendConfirmationCode, signIn } from "./cognito";
import ConfirmCodeForm from "./ConfirmCodeForm";
import { saveSession } from "./session";

/**
 * Sign-in form fields — Figma D02 (node 3337:42 onward). CLOUDAPPG5-122.
 *
 * Signs in with Cognito, keeps the tokens (session.ts), then moves on to
 * workspace selection. An account that was never confirmed gets a fresh code
 * and the code step (ConfirmCodeForm) instead of a dead end.
 *
 * Without NEXT_PUBLIC_COGNITO_CLIENT_ID it skips Cognito and goes straight
 * on, so the local demo still works with no AWS account.
 *
 * preventDefault stops the browser's own submit, which would reload /login
 * with the email and password in the address bar.
 */
export default function SignInForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Set when Cognito says the account exists but its email was never confirmed.
  const [needsCode, setNeedsCode] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!COGNITO_CLIENT_ID) {
      router.push("/workspace");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      const tokens = await signIn(email.trim(), password);
      saveSession(tokens, email.trim());
      router.push("/workspace");
    } catch (caught) {
      if (caught instanceof CognitoError && caught.code === "UserNotConfirmedException") {
        // Signed up earlier but never typed the code: send a fresh one and ask for it.
        await resendConfirmationCode(email.trim()).catch(() => {});
        setNeedsCode(true);
        setSubmitting(false);
        return;
      }
      setError(
        caught instanceof CognitoError ? caught.message : "Something went wrong. Please try again.",
      );
      setSubmitting(false);
    }
  }

  if (needsCode) {
    return <ConfirmCodeForm email={email.trim()} password={password} onBack={() => setNeedsCode(false)} />;
  }

  return (
    <form className="flex w-full flex-col gap-[22px]" onSubmit={handleSubmit}>
      <TextField
        id="email"
        name="email"
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        iconSrc="/icons/mail.svg"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />

      <TextField
        id="password"
        name="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        placeholder="••••••••••"
        iconSrc="/icons/lock.svg"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />

      <div className="flex items-center justify-between">
        <label
          htmlFor="remember"
          className="flex items-center gap-2.5 text-[14px] tracking-[-0.28px] text-foreground"
        >
          <span className="relative inline-flex size-5 shrink-0">
            <input
              id="remember"
              name="remember"
              type="checkbox"
              defaultChecked
              className="peer size-5 appearance-none rounded-[5px] border border-border checked:border-brand checked:bg-brand"
            />
            <Image
              src="/icons/check-small.svg"
              alt=""
              width={13}
              height={13}
              className="pointer-events-none absolute inset-0 m-auto hidden peer-checked:block"
            />
          </span>
          Remember me
        </label>

        <Link
          href="/forgot-password"
          className="-my-1.5 py-1.5 text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Forgot password?
        </Link>
      </div>

      {error && (
        <p role="alert" className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
          {error}
        </p>
      )}

      <Button type="submit" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign In"}
      </Button>
    </form>
  );
}
