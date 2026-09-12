import Image from "next/image";
import Link from "next/link";

/**
 * Marketing site header — Figma 3313:1716 (desktop) and 3399:172 (mobile M01).
 *
 * Mobile shows only "Sign In"; the "Get Started" button appears from md up,
 * because on mobile the hero's full-width button already covers that action.
 */
export default function Header() {
  return (
    <header className="flex h-16 items-center justify-between bg-brand pr-4 pl-5 md:h-auto md:px-8 md:py-4">
      <Link href="/" className="flex items-center gap-1 md:gap-[5px]">
        <Image
          src="/warranty-logo.svg"
          alt=""
          width={48}
          height={48}
          priority
          className="size-9 md:size-12"
        />
        <span className="text-[20px] font-bold text-brand-foreground md:text-[28px]">
          WarrantyTrack
        </span>
      </Link>

      <nav className="flex items-center gap-6">
        <Link
          href="/login"
          className="flex h-[38px] items-center justify-center rounded-lg bg-white px-[18px] text-[14px] font-bold tracking-[-0.28px] text-brand md:h-[60px] md:px-10 md:text-[18px] md:tracking-[-0.36px]"
        >
          Sign In
        </Link>
        <Link
          href="/signup"
          className="hidden h-[60px] items-center justify-center gap-2.5 rounded-lg border border-white px-6 text-[18px] font-bold tracking-[-0.36px] text-brand-foreground md:flex"
        >
          Get Started
          <Image src="/icon-arrow-right.svg" alt="" width={20} height={18} />
        </Link>
      </nav>
    </header>
  );
}
