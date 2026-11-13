"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { signedInUser } from "@/features/auth/session";
import type { NotificationSettings } from "@/types";

import {
  REMIND_DAY_OPTIONS,
  getNotificationSettings,
  saveNotificationSettings,
} from "./notificationSettings";
import SettingsTabs from "./SettingsTabs";

interface ToggleProps {
  checked: boolean;
  id: string;
  label: string;
  disabled?: boolean;
  onChange: () => void;
}

function Toggle({ checked, id, label, disabled, onChange }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={`relative h-[26px] w-11 shrink-0 rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 ${checked ? "bg-brand" : "bg-border"}`}
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
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  icon: string;
  checked: boolean;
  disabled?: boolean;
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
        disabled={disabled}
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

/**
 * Settings → Notifications (CLOUDAPPG5-124, saved since CLOUDAPPG5-145).
 * Every change is saved straight away; the daily scan reads these settings
 * to decide whether and when to remind this person (GitHub #82).
 */
export default function SettingsNotifications() {
  // null until the saved settings have loaded; the controls wait for them.
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [saving, setSaving] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);
  // Numbers each save, so a slow early reply can't overwrite a later choice.
  const latestSave = useRef(0);

  // Where expiry emails go: the address the user signed in with. It lives in
  // localStorage, which only exists in the browser, so it is read after the
  // first render (the same way as AppTopBar).
  const [alertEmail, setAlertEmail] = useState<string | null>(null);

  useEffect(() => {
    const signedIn = signedInUser();
    // Reading browser storage is a one-off sync with an outside system.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (signedIn) setAlertEmail(signedIn.email);
  }, []);

  useEffect(() => {
    let ignore = false;
    getNotificationSettings()
      .then((loaded) => {
        if (!ignore) setSettings(loaded);
      })
      .catch((caught: unknown) => {
        if (!ignore) setError(caught instanceof Error ? caught.message : "Couldn't load your settings.");
      });
    return () => {
      ignore = true;
    };
  }, []);

  /** Show the change at once, save it, and undo it on screen if saving fails. */
  async function update(next: NotificationSettings) {
    if (!settings) return;
    const previous = settings;
    const thisSave = ++latestSave.current;
    setSettings(next);
    setSaving("saving");
    setError(null);
    try {
      const saved = await saveNotificationSettings(next);
      if (thisSave !== latestSave.current) return; // A newer change is on its way.
      setSettings(saved);
      setSaving("saved");
    } catch (caught) {
      if (thisSave !== latestSave.current) return;
      setSettings(previous);
      setSaving("idle");
      setError(caught instanceof Error ? caught.message : "Couldn't save your settings.");
    }
  }

  function toggleDay(day: number) {
    if (!settings) return;
    const days = settings.remind_days.includes(day)
      ? settings.remind_days.filter((item) => item !== day)
      : [...settings.remind_days, day];
    update({ ...settings, remind_days: days });
  }

  const loading = settings === null;

  return (
    <div className="min-h-screen bg-canvas">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-[14px] md:gap-5 md:px-8 md:pt-8 lg:px-12">
        <div className="flex flex-col gap-1">
          <h1 className="text-[22px] font-bold leading-[27px] tracking-[-0.44px] text-brand">
            Settings
          </h1>
          <p className="text-xs leading-[17px] tracking-[-0.24px] text-muted">
            Choose how you are warned before a warranty expires.{" "}
            <span role="status" className="font-semibold text-brand">
              {saving === "saving" ? "Saving…" : saving === "saved" ? "Saved" : ""}
            </span>
          </p>
        </div>

        <SettingsTabs active="notifications" />

        {error && (
          <p role="alert" className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-2 md:gap-5">
          <SettingCard title="Delivery channels">
            <div className="flex flex-col gap-3">
              <DeliveryChannel
                id="in-app-notifications"
                label="In-app"
                icon="/icons/settings-bell.svg"
                checked={settings?.in_app_enabled ?? true}
                disabled={loading}
                onChange={() => settings && update({ ...settings, in_app_enabled: !settings.in_app_enabled })}
              />
              <div className="h-px w-full bg-border" />
              <DeliveryChannel
                id="email-notifications"
                label="Email"
                icon="/icons/settings-email.svg"
                checked={settings?.email_enabled ?? true}
                disabled={loading}
                onChange={() => settings && update({ ...settings, email_enabled: !settings.email_enabled })}
              />
            </div>
          </SettingCard>

          <SettingCard title="Alert email">
            <div className="flex items-center gap-3 rounded-[11px] border border-border p-[14px]">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-subtle">
                <Image src="/icons/settings-email.svg" alt="" width={20} height={20} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-foreground">
                  {alertEmail ?? "Your sign-in email"}
                </p>
                <p className="text-[11px] leading-4 text-muted">
                  The address you signed in with
                </p>
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
              <p>
                WarrantyTrack sends expiry alerts to this address. Turn them off
                with the Email switch under Delivery channels.
              </p>
            </div>
          </SettingCard>

          <SettingCard title="Alert schedule">
            <div className="flex flex-col gap-2.5">
              <p className="text-[10px] font-bold tracking-[0.6px] text-muted-light">
                REMIND ME BEFORE EXPIRY
              </p>
              <div className="flex flex-wrap gap-2.5">
                {REMIND_DAY_OPTIONS.map((day) => {
                  const selected = settings?.remind_days.includes(day) ?? false;
                  const label = `${day} ${day === 1 ? "day" : "days"}`;
                  return (
                    <button
                      key={day}
                      type="button"
                      aria-pressed={selected}
                      disabled={loading}
                      onClick={() => toggleDay(day)}
                      className={`flex h-[33px] items-center justify-center gap-[7px] rounded-full px-[14px] text-xs font-semibold tracking-[-0.24px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 ${selected ? "bg-brand text-brand-foreground" : "border border-border bg-surface text-muted"}`}
                    >
                      {selected ? (
                        <Image
                          src="/icons/settings-selected.svg"
                          alt=""
                          width={13}
                          height={13}
                        />
                      ) : null}
                      {label}
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] leading-4 text-muted-light">
                With no days chosen you are only told once a warranty has expired.
              </p>
            </div>
          </SettingCard>
        </div>
      </main>
    </div>
  );
}
