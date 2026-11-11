"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";

import { CognitoError, confirmSignUp, resendConfirmationCode, signIn } from "./cognito";
import { saveSession } from "./session";

interface ConfirmCodeFormProps {
  email: string;
  /** The password just typed, so we can sign in straight after confirming. */
  password: string;
  /** Leave this step, e.g. to fix a mistyped email. */
  onBack: () => void;
}

/**
 * "Enter the code from your email" (CLOUDAPPG5-122).
 *
 * Shown after Create Account, and also by Sign In when Cognito says the
 * account was never confirmed (someone signed up, then closed the tab before
 * typing the code). Confirms, signs in, then opens workspace selection.
 */
export default function ConfirmCodeForm({ email, password, onBack }: ConfirmCodeFormProps) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function messageOf(caught: unknown) {
    return caught instanceof CognitoError ? caught.message : "Something went wrong. Please try again.";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      await confirmSignUp(email, code.trim());
      const tokens = await signIn(email, password);
      saveSession(tokens, email);
      router.push("/workspace?new=1");
    } catch (caught) {
      setError(messageOf(caught));
      setSubmitting(false);
    }
  }

  async function handleResend() {
    setError(null);
    setNotice(null);
    try {
      await resendConfirmationCode(email);
      setNotice(`A new code is on its way to ${email}.`);
    } catch (caught) {
      setError(messageOf(caught));
    }
  }

  return (
    <form className="flex w-full flex-col gap-[22px]" onSubmit={handleSubmit}>
      <p className="text-[14px] leading-5 tracking-[-0.28px] text-foreground">
        We sent a 6-digit code to <span className="font-semibold">{email}</span>. Enter it to finish
        creating your account.
      </p>

      <TextField
        id="confirm-code"
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

      <Button type="submit" disabled={submitting}>
        {submitting ? "Checking…" : "Verify and continue"}
      </Button>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={handleResend}
          className="text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Send a new code
        </button>
        <button
          type="button"
          onClick={onBack}
          className="text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Use a different email
        </button>
      </div>
    </form>
  );
}
