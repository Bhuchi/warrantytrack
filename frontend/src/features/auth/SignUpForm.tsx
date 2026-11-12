"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";
import { COGNITO_CLIENT_ID } from "@/lib/config";

import { CognitoError, signUp } from "./cognito";
import ConfirmCodeForm from "./ConfirmCodeForm";

/**
 * Create-account form, in two steps (CLOUDAPPG5-122):
 *
 * 1. details: name, email, password. Cognito creates the account and emails
 *    a 6-digit code.
 * 2. code: ConfirmCodeForm. The user types the code, then we sign them in
 *    with the password they just chose, so they never retype it.
 *
 * NOTE: Figma D02 only designs the Sign In tab, so these fields, the terms
 * checkbox and the code step are a best guess built to match the sign-in
 * card. Re-check against the real frames once they exist.
 *
 * Without NEXT_PUBLIC_COGNITO_CLIENT_ID it skips Cognito and goes straight to
 * the new-user workspace screen, so the local demo still works.
 */
export default function SignUpForm() {
  const router = useRouter();
  const [step, setStep] = useState<"details" | "code">("details");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function showError(caught: unknown) {
    setError(
      caught instanceof CognitoError ? caught.message : "Something went wrong. Please try again.",
    );
    setSubmitting(false);
  }

  async function handleDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!COGNITO_CLIENT_ID) {
      router.push("/workspace?new=1");
      return;
    }
    if (password !== confirmPassword) {
      setError("The two passwords do not match.");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      await signUp(email.trim(), password, name.trim());
      setStep("code");
      setSubmitting(false);
    } catch (caught) {
      showError(caught);
    }
  }

  const errorMessage = error && (
    <p role="alert" className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
      {error}
    </p>
  );

  if (step === "code") {
    return (
      <ConfirmCodeForm
        email={email.trim()}
        password={password}
        onBack={() => {
          setStep("details");
          setError(null);
        }}
      />
    );
  }

  return (
    <form className="flex w-full flex-col gap-[22px]" onSubmit={handleDetails}>
      <TextField
        id="name"
        name="name"
        label="Full name"
        type="text"
        autoComplete="name"
        placeholder="Jane Doe"
        iconSrc="/icons/user.svg"
        required
        value={name}
        onChange={(event) => setName(event.target.value)}
      />

      <TextField
        id="signup-email"
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
        id="signup-password"
        name="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        placeholder="At least 8 characters"
        iconSrc="/icons/lock.svg"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />

      <TextField
        id="confirm-password"
        name="confirmPassword"
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        placeholder="Re-enter your password"
        iconSrc="/icons/lock.svg"
        required
        value={confirmPassword}
        onChange={(event) => setConfirmPassword(event.target.value)}
      />

      <label
        htmlFor="terms"
        className="flex items-start gap-2.5 text-[14px] leading-5 tracking-[-0.28px] text-foreground"
      >
        <span className="relative inline-flex size-5 shrink-0">
          <input
            id="terms"
            name="terms"
            type="checkbox"
            required
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
        <span>
          I agree to the{" "}
          <Link href="/terms" className="font-semibold text-brand">
            Terms
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="font-semibold text-brand">
            Privacy Policy
          </Link>
          .
        </span>
      </label>

      {errorMessage}

      <Button type="submit" disabled={submitting}>
        {submitting ? "Creating account…" : "Create Account"}
      </Button>
    </form>
  );
}
