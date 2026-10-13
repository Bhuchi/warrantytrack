import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
};

/**
 * Placeholder so /dashboard resolves and the navigation can be used.
 * FE-06 replaces this with the real screen (Figma D04 / M04).
 */
export default function DashboardPage() {
  return (
    <main className="flex-1 px-6 py-6 md:px-8">
      <h1 className="text-[29px] leading-[38px] font-bold tracking-[-0.58px] text-brand md:text-[44px] md:leading-[54px] md:tracking-[-0.88px]">
        Dashboard
      </h1>
      <p className="mt-2 text-[14px] leading-[22px] tracking-[-0.28px] text-muted md:text-[18px] md:leading-7">
        Placeholder. The real dashboard is FE-06 — see{" "}
        <code className="rounded bg-brand-subtle px-1 py-0.5 text-brand">
          docs/frontend-plan.md
        </code>
        .
      </p>
    </main>
  );
}
