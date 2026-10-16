import Image from "next/image";
import Link from "next/link";

import TextField from "@/components/TextField";

/**
 * Create-account form.
 *
 * NOTE: Figma D02 only designs the Sign In tab, so these fields and the terms
 * checkbox are a best guess built to match the sign-in card. Re-check against
 * the real frame once it exists.
 *
 * TODO: does not submit yet — same wiring plan as SignInForm.
 */
export default function SignUpForm() {
  return (
    <form className="flex w-full flex-col gap-[22px]">
      <TextField
        id="name"
        name="name"
        label="Full name"
        type="text"
        autoComplete="name"
        placeholder="Jane Doe"
        iconSrc="/icons/user.svg"
      />

      <TextField
        id="signup-email"
        name="email"
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        iconSrc="/icons/mail.svg"
      />

      <TextField
        id="signup-password"
        name="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        placeholder="At least 8 characters"
        iconSrc="/icons/lock.svg"
      />

      <TextField
        id="confirm-password"
        name="confirmPassword"
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        placeholder="Re-enter your password"
        iconSrc="/icons/lock.svg"
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

      <button
        type="submit"
        className="h-14 w-full rounded-[10px] bg-brand text-[17px] font-bold tracking-[-0.34px] text-brand-foreground md:h-[54px] md:rounded-lg"
      >
        Create Account
      </button>
    </form>
  );
}
