import type { Metadata } from "next";
import Link from "next/link";
import PasswordResetForm from "@/features/auth/PasswordResetForm";

export const metadata: Metadata = { title: "Reset password" };

export default function ForgotPasswordPage() {
  return <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
    <div className="w-full max-w-[480px] rounded-2xl border border-border bg-surface p-8 shadow-card">
      <h1 className="mb-3 text-[26px] font-bold text-foreground">Reset your password</h1>
      <p className="mb-6 text-[15px] text-muted">We’ll email a verification code to your account.</p>
      <PasswordResetForm />
      <Link href="/login" className="mt-5 block text-center text-[14px] font-semibold text-brand">
        Back to sign in
      </Link>
    </div>
  </main>;
}
