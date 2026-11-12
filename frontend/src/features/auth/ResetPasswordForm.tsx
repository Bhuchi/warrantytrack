"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";

import { CognitoError, confirmForgotPassword, forgotPassword, signIn } from "./cognito";
import { saveSession } from "./session";

function messageOf(caught: unknown) {
  return caught instanceof CognitoError ? caught.message : "Something went wrong. Please try again.";
}

/**
 * "Forgot password?" from Sign In (CLOUDAPPG5-125). Two steps on one screen:
 *
 * 1. Email: Cognito sends a reset code.
 * 2. Code and new password: Cognito sets it, then we sign in straight away.
 *
 * Step 1 never says whether the account exists (see forgotPassword).
 */
export default function ResetPasswordForm() {
  const router = useRouter();
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function sendCode(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      await forgotPassword(email.trim());
      setStep("reset");
      setNotice(`If an account exists for ${email.trim()}, we sent it a 6-digit code.`);
    } catch (caught) {
      setError(messageOf(caught));
    }
    setSubmitting(false);
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await confirmForgotPassword(email.trim(), code.trim(), password);
      const tokens = await signIn(email.trim(), password);
      saveSession(tokens, email.trim());
      router.push("/workspace");
    } catch (caught) {
      setError(messageOf(caught));
      setSubmitting(false);
    }
  }

  const messages = (
    <>
      {error && (
        <p role="alert" className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-[10px] bg-brand-subtle px-4 py-3 text-[13px] text-brand">
          {notice}
        </p>
      )}
    </>
  );

  if (step === "email") {
    return (
      <form className="flex w-full flex-col gap-[22px]" onSubmit={sendCode}>
        <p className="text-[14px] leading-5 tracking-[-0.28px] text-foreground">
          Enter the email you signed up with. We&apos;ll send you a code to set a new password.
        </p>
        <TextField
          id="reset-email"
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
        {messages}
        <Button type="submit" disabled={submitting}>
          {submitting ? "Sending…" : "Send code"}
        </Button>
        <Link href="/login" className="-my-1.5 py-1.5 text-center text-[14px] font-semibold tracking-[-0.28px] text-brand">
          Back to sign in
        </Link>
      </form>
    );
  }

  return (
    <form className="flex w-full flex-col gap-[22px]" onSubmit={resetPassword}>
      <TextField
        id="reset-code"
        name="code"
        label="Verification code"
        inputMode="numeric"
        autoComplete="one-time-code"
        placeholder="123456"
        iconSrc="/icons/mail.svg"
        required
        value={code}
        onChange={(event) => setCode(event.target.value)}
      />
      <TextField
        id="new-password"
        name="password"
        label="New password"
        type="password"
        autoComplete="new-password"
        placeholder="••••••••••"
        iconSrc="/icons/lock.svg"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <TextField
        id="confirm-new-password"
        name="confirmPassword"
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        placeholder="••••••••••"
        iconSrc="/icons/lock.svg"
        required
        value={confirm}
        onChange={(event) => setConfirm(event.target.value)}
      />
      {messages}
      <Button type="submit" disabled={submitting}>
        {submitting ? "Saving…" : "Set new password"}
      </Button>
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => sendCode()}
          disabled={submitting}
          className="-my-1.5 py-1.5 text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Send a new code
        </button>
        <button
          type="button"
          onClick={() => {
            setStep("email");
            setError(null);
            setNotice(null);
          }}
          className="-my-1.5 py-1.5 text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Use a different email
        </button>
      </div>
    </form>
  );
}
