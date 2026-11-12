"use client";

import { useEffect, useRef, type ReactNode } from "react";

import Card from "@/components/Card";

interface ModalProps {
  /** Whether the modal is showing. The screen that uses it owns this value. */
  open: boolean;
  /** Called on Escape or a tap on the dimmed background. */
  onClose: () => void;
  title: string;
  /** Body text under the title. */
  children: ReactNode;
  /** The buttons along the bottom, e.g. Cancel and Discard. */
  actions: ReactNode;
}

/**
 * Centred dialog over a dimmed page. Figma: Modal component (3567:2), shown
 * over D06 (3567:11) and on mobile (3567:233).
 */
export default function Modal({ open, onClose, title, children, actions }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // On open: remember what had focus (usually the button that opened us), move
  // focus into the dialog and stop the page behind from scrolling. The cleanup
  // runs however the modal closes, and gives focus back to that element.
  // Only `open` is a dependency, so this cannot re-run while the modal is open.
  useEffect(() => {
    if (!open) return;

    const opener = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = "";
      opener?.focus();
    };
  }, [open]);

  // While open: Escape closes, and Tab wraps around inside the dialog instead
  // of moving to the hidden page behind it.
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !dialogRef.current) return;

      const items = dialogRef.current.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled]), input:not([disabled]), select, textarea",
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === dialogRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-5">
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/50"
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        className="relative w-full max-w-[400px] outline-none"
      >
        <Card className="flex flex-col gap-5 p-6 shadow-card">
          <div className="flex flex-col gap-2">
            <h2
              id="modal-title"
              className="text-[18px] font-bold tracking-[-0.36px] text-foreground"
            >
              {title}
            </h2>
            <div className="text-[14px] leading-5 tracking-[-0.28px] text-muted">
              {children}
            </div>
          </div>
          <div className="flex gap-3">{actions}</div>
        </Card>
      </div>
    </div>
  );
}
