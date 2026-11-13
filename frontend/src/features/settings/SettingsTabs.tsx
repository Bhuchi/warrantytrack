import Link from "next/link";

type SettingsTab = "notifications" | "team";

/** Tabs that have a page. Profile and Workspace are still placeholders. */
const TABS: { id: SettingsTab; label: string; href: string }[] = [
  { id: "notifications", label: "Notifications", href: "/settings" },
  { id: "team", label: "Team", href: "/settings/team" },
];

const PLACEHOLDERS = ["Profile", "Workspace"];

const pill =
  "flex h-[31px] items-center justify-center rounded-full px-[14px] text-xs font-semibold tracking-[-0.24px]";

/** The row of section pills under the Settings title. */
export default function SettingsTabs({ active }: { active: SettingsTab }) {
  return (
    <nav aria-label="Settings sections" className="flex flex-wrap gap-2">
      {TABS.map((tab) =>
        tab.id === active ? (
          <span key={tab.id} aria-current="page" className={`${pill} bg-brand text-brand-foreground`}>
            {tab.label}
          </span>
        ) : (
          <Link
            key={tab.id}
            href={tab.href}
            className={`${pill} border border-border bg-surface text-foreground hover:border-brand hover:text-brand`}
          >
            {tab.label}
          </Link>
        ),
      )}
      {PLACEHOLDERS.map((label) => (
        <span key={label} className={`${pill} border border-border bg-surface text-muted`}>
          {label}
        </span>
      ))}
    </nav>
  );
}
