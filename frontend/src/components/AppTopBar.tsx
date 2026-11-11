import Image from "next/image";
import Link from "next/link";
import SignOutButton from "@/features/auth/SignOutButton";

interface AppTopBarProps {
  /** Signed-in user's email, shown on the right. */
  email: string;
  /** Two-letter avatar initials. */
  initials: string;
}

/** White top bar for signed-in screens — Figma D03 (node 3344:3). */
export default function AppTopBar({ email, initials }: AppTopBarProps) {
  return (
    <header className="flex h-20 items-center justify-between bg-surface px-12">
      <Link href="/" className="flex items-center gap-3">
        <Image src="/warranty-logo-blue.svg" alt="" width={36} height={36} />
        <span className="text-[22px] font-bold text-brand">WarrantyTrack</span>
      </Link>

      <div className="flex items-center gap-2.5">
        <span className="text-[14px] tracking-[-0.28px] text-muted">
          {email}
        </span>
        <span className="flex size-9 items-center justify-center rounded-full bg-brand-subtle text-[13px] font-bold text-brand">
          {initials}
        </span>
        <SignOutButton className="text-[14px] font-semibold tracking-[-0.28px] text-brand" />
      </div>
    </header>
  );
}
