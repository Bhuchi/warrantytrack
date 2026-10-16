import Image from "next/image";
import Link from "next/link";

import Button from "@/components/Button";
import TextField from "@/components/TextField";

/**
 * Sign-in form fields — Figma D02 (node 3337:42 onward).
 *
 * TODO: this does not submit anywhere yet. When the Cognito flow exists, add
 * "use client", hold the field values in state, and call a function in
 * features/auth/ that talks to lib/api — never fetch from this component.
 */
export default function SignInForm() {
  return (
    <form className="flex w-full flex-col gap-[22px]">
      <TextField
        id="email"
        name="email"
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        iconSrc="/icons/mail.svg"
      />

      <TextField
        id="password"
        name="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        placeholder="••••••••••"
        iconSrc="/icons/lock.svg"
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
          className="text-[14px] font-semibold tracking-[-0.28px] text-brand"
        >
          Forgot password?
        </Link>
      </div>

      <Button type="submit">Sign In</Button>
    </form>
  );
}
