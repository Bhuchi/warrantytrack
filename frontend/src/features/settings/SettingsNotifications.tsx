"use client";

import Image from "next/image";
import { useState, type ReactNode } from "react";

const reminders = ["60 days", "30 days", "14 days", "7 days", "1 day"] as const;

interface ToggleProps {
  checked: boolean;
  id: string;
  label: string;
  onChange: () => void;
}

function Toggle({ checked, id, label, onChange }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={`relative h-[26px] w-11 shrink-0 rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${checked ? "bg-brand" : "bg-border"}`}
    >
      <span
        className={`absolute left-[3px] top-[3px] size-5 rounded-full bg-white shadow-sm transition-transform ${checked ? "translate-x-[18px]" : "translate-x-0"}`}
      />
    </button>
  );
}

function DeliveryChannel({
  id,
  label,
  icon,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  icon: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <div className="flex min-h-8 items-center gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-brand-subtle">
        <Image src={icon} alt="" width={17} height={17} />
      </span>
      <span id={`${id}-label`} className="min-w-0 flex-1 text-sm font-semibold text-foreground">
        {label}
      </span>
      <Toggle
        id={id}
        label={`${label} notifications`}
        checked={checked}
        onChange={onChange}
      />
    </div>
  );
}

function SettingCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="flex w-full flex-col gap-3 rounded-[14px] border border-border bg-surface px-[18px] py-[14px]">
      <h2 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function SettingsNotifications() {
  const [inAppEnabled, setInAppEnabled] = useState(true);
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [weeklyDigestEnabled, setWeeklyDigestEnabled] = useState(true);
  const [selectedReminders, setSelectedReminders] = useState<string[]>([
    "30 days",
    "14 days",
    "7 days",
  ]);

  function toggleReminder(reminder: string) {
    setSelectedReminders((current) =>
      current.includes(reminder)
        ? current.filter((item) => item !== reminder)
        : [...current, reminder],
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-[14px] md:gap-5 md:px-8 md:pt-8 lg:px-12">
        <div className="flex flex-col gap-1">
          <h1 className="text-[22px] font-bold leading-[27px] tracking-[-0.44px] text-brand">
            Settings
          </h1>
          <p className="text-xs leading-[17px] tracking-[-0.24px] text-muted">
            Choose how you are warned before a warranty expires.
          </p>
        </div>

        <nav aria-label="Settings sections" className="flex flex-wrap gap-2">
          <span
            aria-current="page"
            className="flex h-[31px] items-center justify-center rounded-full bg-brand px-[14px] text-xs font-semibold tracking-[-0.24px] text-brand-foreground"
          >
            Notifications
          </span>
          {["Profile", "Team", "Workspace"].map((tab) => (
            <span
              key={tab}
              className="flex h-[31px] items-center justify-center rounded-full border border-border bg-surface px-[14px] text-xs font-semibold tracking-[-0.24px] text-muted"
            >
              {tab}
            </span>
          ))}
        </nav>

        <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-2 md:gap-5">
          <SettingCard title="Delivery channels">
            <div className="flex flex-col gap-3">
              <DeliveryChannel
                id="in-app-notifications"
                label="In-app"
                icon="/icons/settings-bell.svg"
                checked={inAppEnabled}
                onChange={() => setInAppEnabled((enabled) => !enabled)}
              />
              <div className="h-px w-full bg-border" />
              <DeliveryChannel
                id="email-notifications"
                label="Email"
                icon="/icons/settings-email.svg"
                checked={emailEnabled}
                onChange={() => setEmailEnabled((enabled) => !enabled)}
              />
            </div>
          </SettingCard>

          <SettingCard title="Connected email">
            <p className="-mt-3 text-[11px] leading-4 text-muted-light">
              Personal Workspace
            </p>
            <div className="flex items-center gap-3 rounded-[11px] border-[1.5px] border-green-600 p-[14px]">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-canvas text-xl font-bold text-[#4285f4]">
                G
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground">Gmail</span>
                  <Image
                    src="/icons/settings-connected-dot.svg"
                    alt=""
                    width={7}
                    height={7}
                  />
                  <span className="text-[11px] font-semibold text-status-active">
                    Connected
                  </span>
                </div>
                <p className="truncate text-[11px] leading-4 text-muted">
                  you@example.com
                </p>
              </div>
            </div>
            <div className="flex gap-2.5">
              <div className="flex h-[42px] flex-1 items-center justify-center gap-2 rounded-[9px] border border-border text-[13px] font-semibold text-brand">
                <Image
                  src="/icons/settings-send-test.svg"
                  alt=""
                  width={15}
                  height={15}
                />
                Send test
              </div>
              <div className="flex h-[42px] flex-1 items-center justify-center rounded-[9px] border border-border text-[13px] font-semibold text-muted">
                Disconnect
              </div>
            </div>
            <div className="flex items-start gap-2 text-[11px] leading-4 text-muted-light">
              <Image
                src="/icons/settings-permission.svg"
                alt=""
                width={14}
                height={14}
                className="mt-0.5 shrink-0"
              />
              <p>Send-only permission — WarrantyTrack never reads your inbox.</p>
            </div>
          </SettingCard>

          <SettingCard title="Alert schedule">
            <div className="flex flex-col gap-2.5">
              <p className="text-[10px] font-bold tracking-[0.6px] text-muted-light">
                REMIND ME BEFORE EXPIRY
              </p>
              <div className="flex flex-wrap gap-2.5">
                {reminders.map((reminder) => {
                  const selected = selectedReminders.includes(reminder);
                  return (
                    <button
                      key={reminder}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => toggleReminder(reminder)}
                      className={`flex h-[33px] items-center justify-center gap-[7px] rounded-full px-[14px] text-xs font-semibold tracking-[-0.24px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${selected ? "bg-brand text-brand-foreground" : "border border-border bg-surface text-muted"}`}
                    >
                      {selected ? (
                        <Image
                          src="/icons/settings-selected.svg"
                          alt=""
                          width={13}
                          height={13}
                        />
                      ) : null}
                      {reminder}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="h-px w-full bg-border" />
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold leading-[17px] text-foreground">
                  Weekly digest
                </p>
                <p className="text-[11px] leading-[13px] text-muted-light">
                  Monday summary at 09:00
                </p>
              </div>
              <Toggle
                id="weekly-digest"
                label="Weekly digest"
                checked={weeklyDigestEnabled}
                onChange={() => setWeeklyDigestEnabled((enabled) => !enabled)}
              />
            </div>
          </SettingCard>
        </div>
      </main>
    </div>
  );
}
