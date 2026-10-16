import Link from "next/link";

/** Sign In / Create Account tabs on the auth card — Figma D02 (node 3337:35). */

const TABS = [
  { id: "signin", label: "Sign In", href: "/login" },
  { id: "signup", label: "Create Account", href: "/signup" },
] as const;

interface AuthTabsProps {
  /** Which tab the current page represents. */
  active: (typeof TABS)[number]["id"];
}

export default function AuthTabs({ active }: AuthTabsProps) {
  return (
    <nav className="flex w-full">
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <Link
            key={tab.id}
            href={tab.href}
            aria-current={isActive ? "page" : undefined}
            className="flex flex-1 flex-col items-center gap-3 pt-1"
          >
            <span
              className={`text-[15px] tracking-[-0.3px] md:text-[16px] md:tracking-[-0.32px] ${
                isActive ? "font-bold text-brand" : "font-medium text-muted"
              }`}
            >
              {tab.label}
            </span>
            <span
              className={
                isActive ? "h-[3px] w-full bg-brand" : "h-[1.5px] w-full bg-border"
              }
            />
          </Link>
        );
      })}
    </nav>
  );
}
