import type { Metadata } from "next";

import BrandPanel from "@/features/auth/BrandPanel";
import ResetPasswordForm from "@/features/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Reset Password",
};

/** "Forgot password?" from Sign In. No Figma frame; uses the sign-in card layout (D02). */
export default function ForgotPasswordPage() {
  return (
    <>
      <BrandPanel
        title="Locked out?"
        subtitle="Reset your password with a code sent to your email, then carry on where you left off."
      />

      <main className="-mt-11 flex flex-1 justify-center md:mt-0 md:px-8 md:pt-[158px] md:pb-16">
        <div className="flex h-fit w-full flex-col gap-[18px] rounded-t-[28px] bg-surface px-6 pt-6 pb-7 md:w-full md:max-w-[480px] md:gap-[22px] md:rounded-2xl md:border md:border-border md:px-10 md:pt-10 md:pb-9 md:shadow-card">
          <div className="flex flex-col gap-2">
            <h2 className="text-[22px] font-bold tracking-[-0.44px] text-foreground md:text-[26px] md:tracking-[-0.52px]">
              Reset your password
            </h2>
          </div>
          <ResetPasswordForm />
        </div>
      </main>
    </>
  );
}
