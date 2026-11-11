"use client";

import { useState, type FormEvent } from "react";
import Button from "@/components/Button";
import TextField from "@/components/TextField";
import { COGNITO_ENABLED } from "@/lib/config";
import { authError, finishPasswordReset, startPasswordReset } from "./cognito";

export default function PasswordResetForm() {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<"email" | "code" | "done">("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!COGNITO_ENABLED) {
      setError("Password reset requires Cognito configuration.");
      return;
    }
    setBusy(true);
    try {
      if (step === "email") {
        await startPasswordReset(email);
        setStep("code");
      } else {
        await finishPasswordReset(email, code, password);
        setStep("done");
      }
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setBusy(false);
    }
  }
  if (step === "done") return <p role="status" className="text-[15px] text-foreground">
    Password updated. You can sign in now.
  </p>;
  return <form className="flex flex-col gap-[22px]" onSubmit={submit}>
    {step === "email" ? <TextField id="reset-email" label="Email" type="email" autoComplete="email"
      iconSrc="/icons/mail.svg" required value={email}
      onChange={(event) => setEmail(event.target.value)} /> : <>
      <p className="text-[14px] text-muted">Enter the code sent to {email} and choose a new password.</p>
      <TextField id="reset-code" label="Verification code" type="text" autoComplete="one-time-code"
        iconSrc="/icons/mail.svg" required value={code} onChange={(event) => setCode(event.target.value)} />
      <TextField id="reset-password" label="New password" type="password" autoComplete="new-password"
        iconSrc="/icons/lock.svg" required value={password}
        onChange={(event) => setPassword(event.target.value)} />
    </>}
    {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
    <Button type="submit" disabled={busy}>{busy ? "Please wait…" : step === "email" ? "Send code" : "Update password"}</Button>
  </form>;
}
