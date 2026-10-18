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

  // Same pattern as NavPanel: while open, move focus into the dialog, stop the
  // page behind from scrolling, and listen for Escape. The returned function
  // undoes all three when the modal closes.
  useEffect(() => {
    if (!open) return;

    dialogRef.current?.focus();
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
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
