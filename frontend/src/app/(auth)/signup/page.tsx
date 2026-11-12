import type { Metadata } from "next";
import Image from "next/image";

import AuthTabs from "@/features/auth/AuthTabs";
import BrandPanel from "@/features/auth/BrandPanel";
import SignUpForm from "@/features/auth/SignUpForm";
import SocialLogins from "@/features/auth/SocialLogins";

export const metadata: Metadata = {
  title: "Create Account",
};

/** Sign-up screen. No Figma frame yet — mirrors D02's sign-in card. */
export default function SignUpPage() {
  return (
    <>
      <BrandPanel
        title="Start in minutes."
        subtitle="Create an account to store receipts, track warranties and get expiry alerts before they lapse."
      />

      <main className="-mt-11 flex flex-1 justify-center md:mt-0 md:px-8 md:pt-[158px] md:pb-16">
        <div className="flex h-fit w-full flex-col gap-[18px] rounded-t-[28px] bg-surface px-6 pt-6 pb-7 md:w-full md:max-w-[480px] md:gap-[22px] md:rounded-2xl md:border md:border-border md:px-10 md:pt-10 md:pb-9 md:shadow-card">
          <div className="hidden flex-col gap-2 md:flex">
            <h2 className="text-[26px] font-bold tracking-[-0.52px] text-foreground">
              Create your account
            </h2>
            <p className="text-[15px] tracking-[-0.3px] text-muted">
              It only takes a minute to get set up.
            </p>
          </div>

          <AuthTabs active="signup" />
          <SignUpForm />
          <SocialLogins />

          <div className="flex items-start gap-3 rounded-[10px] bg-brand-subtle px-4 py-3.5 md:rounded-lg">
            <Image
              src="/icons/shield-info.svg"
              alt=""
              width={20}
              height={20}
              className="shrink-0"
            />
            <p className="text-[13px] leading-5 tracking-[-0.26px] text-brand">
              After signing up you can create a Personal Workspace or join an
              Organization Workspace.
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
