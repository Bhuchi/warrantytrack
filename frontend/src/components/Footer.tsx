import Link from "next/link";

/**
 * Marketing site footer — Figma 3313:1662 (desktop) and 3399:206 (mobile M01).
 *
 * The two designs order things differently: desktop puts Privacy/Terms and the
 * social icons up beside the wordmark and leaves Contacts alone underneath,
 * while mobile drops the socials and puts all three links below the divider.
 * Privacy and Terms therefore appear twice, each hidden at the other breakpoint.
 */

// TODO: swap "#" for the real profile URLs once the accounts exist.
const SOCIAL_LINKS = [
  {
    name: "Twitter",
    href: "#",
    path: "M21.543 7.104c.015.211.015.423.015.636 0 6.507-4.954 14.01-14.01 14.01v-.003A13.94 13.94 0 0 1 0 19.539a9.88 9.88 0 0 0 7.287-2.041 4.93 4.93 0 0 1-4.6-3.42 4.916 4.916 0 0 0 2.223-.084A4.926 4.926 0 0 1 .96 9.167v-.062a4.887 4.887 0 0 0 2.235.616A4.928 4.928 0 0 1 1.67 3.148 13.98 13.98 0 0 0 11.82 8.292a4.929 4.929 0 0 1 8.39-4.49 9.868 9.868 0 0 0 3.128-1.196 4.941 4.941 0 0 1-2.165 2.724A9.828 9.828 0 0 0 24 4.555a10.019 10.019 0 0 1-2.457 2.549z",
  },
  {
    name: "Facebook",
    href: "#",
    path: "M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z",
  },
  {
    name: "TikTok",
    href: "#",
    path: "M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z",
  },
];

export default function Footer() {
  return (
    <footer className="bg-brand text-brand-foreground">
      <div className="mx-auto w-full max-w-[1202px] px-6 py-5 md:px-8 md:py-0">
        <div className="flex items-center justify-between pb-3.5 md:pt-[47px] md:pb-9">
          <span className="text-[17px] font-bold md:text-[24px] md:tracking-[-0.29px]">
            WarrantyTrack
          </span>

          <nav className="hidden items-center gap-10 md:flex">
            <Link href="/privacy" className="text-[16px] hover:opacity-80">
              Privacy Policy
            </Link>
            <Link href="/terms" className="text-[16px] hover:opacity-80">
              Terms
            </Link>

            <ul className="flex items-center gap-6">
              {SOCIAL_LINKS.map((social) => (
                <li key={social.name}>
                  <Link
                    href={social.href}
                    aria-label={social.name}
                    className="block hover:opacity-80"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="size-[18px] fill-current"
                      aria-hidden="true"
                    >
                      <path d={social.path} />
                    </svg>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <span className="block h-px w-full bg-white/30" />

        <nav className="flex gap-5 pt-3.5 text-[12px] tracking-[-0.24px] opacity-80 md:gap-0 md:pt-[49px] md:pb-[34px] md:text-[16px] md:tracking-normal md:opacity-100">
          <Link href="/privacy" className="hover:opacity-80 md:hidden">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:opacity-80 md:hidden">
            Terms
          </Link>
          <Link href="/contacts" className="hover:opacity-80">
            Contacts
          </Link>
        </nav>
      </div>
    </footer>
  );
}
