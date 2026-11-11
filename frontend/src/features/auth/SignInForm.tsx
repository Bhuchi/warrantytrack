"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import TextField from "@/components/TextField";
import { AUTH_REQUIRED, COGNITO_ENABLED } from "@/lib/config";
import { authError, confirmEmail, finishSignInChallenge, resendConfirmationCode, signInWithEmail } from "./cognito";

type Step = "credentials" | "confirm-email" | "new-password" | "challenge-code";

export default function SignInForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [step, setStep] = useState<Step>("credentials");
  const [challenge, setChallenge] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!COGNITO_ENABLED) {
      if (AUTH_REQUIRED) setError("Cognito pool and client IDs are missing from this deployment.");
      else router.push("/workspace");
      return;
    }
    setBusy(true);
    try {
      if (step === "confirm-email") await confirmEmail(email, challenge);
      const result = step === "credentials" || step === "confirm-email"
        ? await signInWithEmail(email, password, remember)
        : await finishSignInChallenge(challenge);
      if (result.isSignedIn) {
        router.replace("/workspace");
        return;
      }
      switch (result.nextStep.signInStep) {
        case "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED":
          setStep("new-password");
          break;
        case "CONFIRM_SIGN_IN_WITH_SMS_CODE":
        case "CONFIRM_SIGN_IN_WITH_EMAIL_CODE":
        case "CONFIRM_SIGN_IN_WITH_TOTP_CODE":
          setStep("challenge-code");
          break;
        default:
          setError("This sign-in step is not available here. Contact your administrator.");
      }
    } catch (cause) {
      if (cause instanceof Error && cause.name === "UserNotConfirmedException") {
        setStep("confirm-email");
        setError("Confirm your email using the code Cognito sent you.");
      } else setError(authError(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="flex w-full flex-col gap-[22px]" onSubmit={submit}>
      {step === "credentials" ? <>
        <TextField id="email" name="email" label="Email" type="email" autoComplete="email"
          placeholder="you@example.com" iconSrc="/icons/mail.svg" required value={email}
          onChange={(event) => setEmail(event.target.value)} />
        <TextField id="password" name="password" label="Password" type="password"
          autoComplete="current-password" placeholder="••••••••••" iconSrc="/icons/lock.svg"
          required value={password} onChange={(event) => setPassword(event.target.value)} />
        <div className="flex items-center justify-between">
          <label htmlFor="remember" className="flex items-center gap-2.5 text-[14px] tracking-[-0.28px] text-foreground">
            <span className="relative inline-flex size-5 shrink-0">
              <input id="remember" name="remember" type="checkbox" checked={remember}
                onChange={(event) => setRemember(event.target.checked)}
                className="peer size-5 appearance-none rounded-[5px] border border-border checked:border-brand checked:bg-brand" />
              <Image src="/icons/check-small.svg" alt="" width={13} height={13}
                className="pointer-events-none absolute inset-0 m-auto hidden peer-checked:block" />
            </span>
            Remember me
          </label>
          <Link href="/forgot-password" className="text-[14px] font-semibold tracking-[-0.28px] text-brand">
            Forgot password?
          </Link>
        </div>
      </> : <>
        <p className="text-[14px] text-muted">
          {step === "new-password" ? "Set a new password to finish signing in." : "Enter the verification code sent to you."}
        </p>
        <TextField id="challenge" label={step === "new-password" ? "New password" : "Verification code"}
          iconSrc={step === "new-password" ? "/icons/lock.svg" : "/icons/mail.svg"}
          type={step === "new-password" ? "password" : "text"} required value={challenge}
          autoComplete={step === "new-password" ? "new-password" : "one-time-code"}
          onChange={(event) => setChallenge(event.target.value)} />
      </>}
      {step === "confirm-email" && <button type="button" className="text-left text-[14px] font-semibold text-brand"
        onClick={() => void resendConfirmationCode(email).catch((cause) => setError(authError(cause)))}>
        Resend confirmation code
      </button>}
      {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
      <Button type="submit" disabled={busy}>{busy ? "Please wait…" : step === "credentials" ? "Sign In" : "Continue"}</Button>
    </form>
  );
}
