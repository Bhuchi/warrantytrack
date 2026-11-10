"use client";

import Image from "next/image";
import { useMemo, useState } from "react";

type NotificationCategory = "Warranties" | "Assets" | "System";
type NotificationFilter = "All" | NotificationCategory;
type NotificationGroup = "TODAY" | "YESTERDAY";

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  time: string;
  group: NotificationGroup;
  category: NotificationCategory;
  icon: string;
  iconBackground: string;
  isRead: boolean;
}

const initialNotifications: NotificationItem[] = [
  {
    id: "warranty-expiring-monitor",
    title: "Warranty Expiring Soon",
    message: 'Dell Monitor 24" expires in 30 days.',
    time: "10:00",
    group: "TODAY",
    category: "Warranties",
    icon: "/icons/notifications-expiring.svg",
    iconBackground: "bg-amber-100",
    isRead: false,
  },
  {
    id: "warranty-expired-printer",
    title: "Warranty Expired",
    message: '"HP Color LaserJet" expired on 10 Jan 2026.',
    time: "09:30",
    group: "TODAY",
    category: "Warranties",
    icon: "/icons/notifications-expired.svg",
    iconBackground: "bg-red-100",
    isRead: false,
  },
  {
    id: "ocr-invoice-complete",
    title: "OCR Completed",
    message: "Processing finished for Invoice_INV-2024-0519.pdf.",
    time: "09:15",
    group: "TODAY",
    category: "System",
    icon: "/icons/notifications-ocr.svg",
    iconBackground: "bg-brand-subtle",
    isRead: false,
  },
  {
    id: "asset-saved-camera",
    title: "Asset Saved",
    message: '"Canon EOS R50" was added to your assets.',
    time: "16:45",
    group: "YESTERDAY",
    category: "Assets",
    icon: "/icons/notifications-saved.svg",
    iconBackground: "bg-green-100",
    isRead: true,
  },
  {
    id: "new-login-location",
    title: "New Login Location",
    message: "IP address 172.64.3.5 (SG).",
    time: "14:10",
    group: "YESTERDAY",
    category: "System",
    icon: "/icons/notifications-login.svg",
    iconBackground: "bg-brand-subtle",
    isRead: true,
  },
];

const filters: NotificationFilter[] = ["All", "Warranties", "Assets", "System"];
const groups: NotificationGroup[] = ["TODAY", "YESTERDAY"];

function NotificationRow({
  item,
  onMarkRead,
}: {
  item: NotificationItem;
  onMarkRead: (id: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onMarkRead(item.id)}
      aria-label={`${item.title}. ${item.isRead ? "Read" : "Unread"}. ${item.message}`}
      className="flex w-full items-start gap-3 py-3 text-left focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      <span
        className={`flex size-[38px] shrink-0 items-center justify-center rounded-[10px] ${item.iconBackground}`}
      >
        <Image src={item.icon} alt="" width={18} height={18} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex min-w-0 items-center gap-2">
          <span className="min-w-0 flex-1 text-[13px] font-semibold tracking-[-0.26px] text-foreground">
            {item.title}
          </span>
          <time className="shrink-0 text-[10px] tracking-[-0.2px] text-muted-light">
            {item.time}
          </time>
          {!item.isRead ? (
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
          {item.message}
        </span>
      </span>
    </button>
  );
}

function NotificationList({
  items,
  onMarkRead,
}: {
  items: NotificationItem[];
  onMarkRead: (id: string) => void;
}) {
  return (
    <section
      aria-label="Notification list"
      className="flex w-full flex-col rounded-[14px] border border-border bg-surface px-4 pb-3 pt-1"
    >
      {groups.map((group) => {
        const groupItems = items.filter((item) => item.group === group);
        if (groupItems.length === 0) return null;

        return (
          <div key={group}>
            <h2 className="pb-2 pt-[14px] text-[10px] font-bold tracking-[0.6px] text-muted-light">
              {group}
            </h2>
            {groupItems.map((item, index) => (
              <div key={item.id}>
                <NotificationRow item={item} onMarkRead={onMarkRead} />
                {index < groupItems.length - 1 ? (
                  <div className="h-px w-full bg-border" />
                ) : null}
              </div>
            ))}
          </div>
        );
      })}
      {items.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted">
          No notifications in this category.
        </p>
      ) : null}
    </section>
  );
}

export default function Notifications() {
  const [notifications, setNotifications] = useState(initialNotifications);
  const [selectedFilter, setSelectedFilter] =
    useState<NotificationFilter>("All");
  const [statusMessage, setStatusMessage] = useState("");

  const unreadCount = notifications.filter((item) => !item.isRead).length;
  const filteredNotifications = useMemo(
    () =>
      notifications.filter(
        (item) => selectedFilter === "All" || item.category === selectedFilter,
      ),
    [notifications, selectedFilter],
  );

  function markRead(id: string) {
    setNotifications((current) =>
      current.map((item) => (item.id === id ? { ...item, isRead: true } : item)),
    );
  }

  function markAllRead() {
    setNotifications((current) => current.map((item) => ({ ...item, isRead: true })));
    setStatusMessage("All notifications marked as read.");
  }

  return (
    <div className="min-h-screen bg-canvas">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 pb-8 pt-4 md:gap-5 md:px-8 md:pt-8 lg:px-12">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand">
              Notifications
            </h1>
            <p className="text-xs tracking-[-0.24px] text-muted">
              {unreadCount} unread
            </p>
          </div>
          <button
            type="button"
            onClick={markAllRead}
            disabled={unreadCount === 0}
            className="flex shrink-0 items-center gap-[7px] rounded-md py-2 text-[13px] font-semibold tracking-[-0.26px] text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-default disabled:opacity-50"
          >
            <Image
              src="/icons/notifications-mark-read.svg"
              alt=""
              width={15}
              height={15}
            />
            Mark all read
          </button>
        </div>

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
                    {notifications.length}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        <NotificationList items={filteredNotifications} onMarkRead={markRead} />

        <button
          type="button"
          className="flex h-[54px] w-full items-center justify-center gap-2.5 rounded-[10px] bg-brand text-base font-bold tracking-[-0.32px] text-brand-foreground md:w-fit md:min-w-56 md:px-8"
        >
          <Image
            src="/icons/notifications-add-asset.svg"
            alt=""
            width={17}
            height={17}
          />
          Add Asset
        </button>
        <p aria-live="polite" className="sr-only">
          {statusMessage}
        </p>
      </main>
    </div>
  );
}
