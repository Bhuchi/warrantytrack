"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { NotificationItem, NotificationType } from "@/types/notifications";

import { getNotifications, markAllNotificationsRead } from "./notificationsApi";

type NotificationCategory = "Warranties" | "Assets";
type NotificationFilter = "All" | NotificationCategory;
type NotificationGroup = "TODAY" | "YESTERDAY" | "EARLIER";

/** How each kind of notification looks. The backend only sends the `type`. */
const TYPE_DISPLAY: Record<
  NotificationType,
  { heading: string; category: NotificationCategory; icon: string; iconBackground: string }
> = {
  warranty_expiring: {
    heading: "Warranty Expiring Soon",
    category: "Warranties",
    icon: "/icons/notifications-expiring.svg",
    iconBackground: "bg-amber-100",
  },
  warranty_expired: {
    heading: "Warranty Expired",
    category: "Warranties",
    icon: "/icons/notifications-expired.svg",
    iconBackground: "bg-red-100",
  },
  asset_assigned: {
    heading: "Asset Assigned",
    category: "Assets",
    icon: "/icons/notifications-saved.svg",
    iconBackground: "bg-green-100",
  },
};

const filters: NotificationFilter[] = ["All", "Warranties", "Assets"];
const groups: NotificationGroup[] = ["TODAY", "YESTERDAY", "EARLIER"];

/** Which heading a notification goes under, by the user's own calendar day. */
function groupOf(iso: string): NotificationGroup {
  const day = new Date(iso).toDateString();
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  if (day === today.toDateString()) return "TODAY";
  if (day === yesterday.toDateString()) return "YESTERDAY";
  return "EARLIER";
}

/** "10:00" for today and yesterday, "3 Nov" for anything older. */
function timeLabel(iso: string, group: NotificationGroup): string {
  const options: Intl.DateTimeFormatOptions =
    group === "EARLIER"
      ? { day: "numeric", month: "short" }
      : { hour: "2-digit", minute: "2-digit", hour12: false };
  return new Intl.DateTimeFormat("en-GB", options).format(new Date(iso));
}

function NotificationRow({ item }: { item: NotificationItem }) {
  const display = TYPE_DISPLAY[item.type];
  const group = groupOf(item.created_at);
  const className =
    "flex w-full items-start gap-3 py-3 text-left focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

  const content = (
    <>
      <span
        className={`flex size-[38px] shrink-0 items-center justify-center rounded-[10px] ${display.iconBackground}`}
      >
        <Image src={display.icon} alt="" width={18} height={18} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex min-w-0 items-center gap-2">
          <span className="min-w-0 flex-1 text-[13px] font-semibold tracking-[-0.26px] text-foreground">
            {display.heading}
          </span>
          <time
            dateTime={item.created_at}
            className="shrink-0 text-[10px] tracking-[-0.2px] text-muted-light"
          >
            {timeLabel(item.created_at, group)}
          </time>
          {!item.read ? (
            <Image
              src="/icons/notifications-unread.svg"
              alt="Unread"
              width={8}
              height={8}
              className="shrink-0"
            />
          ) : null}
        </span>
        <span className="text-[12px] leading-[18px] tracking-[-0.24px] text-muted">
          {item.title}
        </span>
      </span>
    </>
  );

  // The asset is gone if asset_id is null, so there is nothing to open.
  if (item.asset_id === null) {
    return <div className={className}>{content}</div>;
  }
  return (
    <Link href={`/assets/${item.asset_id}`} className={className}>
      {content}
    </Link>
  );
}

function NotificationList({
  items,
  emptyMessage,
}: {
  items: NotificationItem[];
  emptyMessage: string;
}) {
  return (
    <section
      aria-label="Notification list"
      className="flex w-full flex-col rounded-[14px] border border-border bg-surface px-4 pb-3 pt-1"
    >
      {groups.map((group) => {
        const groupItems = items.filter((item) => groupOf(item.created_at) === group);
        if (groupItems.length === 0) return null;

        return (
          <div key={group}>
            <h2 className="pb-2 pt-[14px] text-[10px] font-bold tracking-[0.6px] text-muted-light">
              {group}
            </h2>
            {groupItems.map((item, index) => (
              <div key={item.id}>
                <NotificationRow item={item} />
                {index < groupItems.length - 1 ? (
                  <div className="h-px w-full bg-border" />
                ) : null}
              </div>
            ))}
          </div>
        );
      })}
      {items.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted">{emptyMessage}</p>
      ) : null}
    </section>
  );
}

export default function Notifications() {
  // null = still loading. The list comes from GET /notifications.
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [marking, setMarking] = useState(false);
  const [selectedFilter, setSelectedFilter] =
    useState<NotificationFilter>("All");
  const [statusMessage, setStatusMessage] = useState("");
  const [markError, setMarkError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    getNotifications()
      .then((response) => {
        if (!ignore) setNotifications(response.items);
      })
      .catch(() => {
        if (!ignore) setFailed(true);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const items = useMemo(() => notifications ?? [], [notifications]);
  // Counted from the list, so marking items read updates it with no extra state.
  const unreadCount = items.filter((item) => !item.read).length;
  const filteredNotifications = useMemo(
    () =>
      items.filter(
        (item) =>
          selectedFilter === "All" ||
          TYPE_DISPLAY[item.type].category === selectedFilter,
      ),
    [items, selectedFilter],
  );

  async function markAllRead() {
    setMarking(true);
    setMarkError(null);
    try {
      await markAllNotificationsRead();
      // Only after the server agrees: a 204 has no body, so update our own copy.
      setNotifications((current) =>
        current ? current.map((item) => ({ ...item, read: true })) : current,
      );
      setStatusMessage("All notifications marked as read.");
    } catch {
      setMarkError("Couldn't mark notifications as read. Please try again.");
    } finally {
      setMarking(false);
    }
  }

  let emptyMessage = "No notifications in this category.";
  if (failed) emptyMessage = "Couldn't load notifications. Please refresh the page.";
  else if (notifications === null) emptyMessage = "Loading notifications…";
  else if (items.length === 0) emptyMessage = "No notifications yet.";

  return (
    <div className="min-h-screen bg-canvas">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-4 md:gap-5 md:px-8 md:pt-8 lg:px-12">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand">
              Notifications
            </h1>
            <p className="text-xs tracking-[-0.24px] text-muted">
              {notifications === null ? "…" : `${unreadCount} unread`}
            </p>
          </div>
          <button
            type="button"
            onClick={markAllRead}
            disabled={unreadCount === 0 || marking}
            className="flex shrink-0 items-center gap-[7px] rounded-md py-2 text-[13px] font-semibold tracking-[-0.26px] text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-default disabled:opacity-50"
          >
            <Image
              src="/icons/notifications-mark-read.svg"
              alt=""
              width={15}
              height={15}
            />
            {marking ? "Marking…" : "Mark all read"}
          </button>
        </div>

        {markError ? (
          <p
            role="alert"
            className="rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700"
          >
            {markError}
          </p>
        ) : null}

        <div
          role="group"
          aria-label="Filter notifications"
          className="flex flex-wrap gap-2"
        >
          {filters.map((filter) => {
            const selected = selectedFilter === filter;
            return (
              <button
                key={filter}
                type="button"
                aria-pressed={selected}
                onClick={() => setSelectedFilter(filter)}
                className={`flex min-h-[31px] items-center gap-[7px] rounded-full px-[13px] py-2 text-xs font-semibold tracking-[-0.24px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${selected ? "bg-brand text-brand-foreground" : "border border-border bg-surface text-muted"}`}
              >
                {filter}
                {filter === "All" ? (
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${selected ? "bg-white/20 text-white" : "bg-canvas text-muted"}`}
                  >
                    {items.length}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        <NotificationList items={filteredNotifications} emptyMessage={emptyMessage} />

        <Link
          href="/assets/new"
          className="flex h-[54px] w-full items-center justify-center gap-2.5 rounded-[10px] bg-brand text-base font-bold tracking-[-0.32px] text-brand-foreground md:w-fit md:min-w-56 md:px-8"
        >
          <Image
            src="/icons/notifications-add-asset.svg"
            alt=""
            width={17}
            height={17}
          />
          Add Asset
        </Link>
        <p aria-live="polite" className="sr-only">
          {statusMessage}
        </p>
      </main>
    </div>
  );
}
