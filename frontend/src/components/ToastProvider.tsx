"use client";

import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import Toast, { type ToastProps } from "@/components/Toast";

/** What a page asks for: everything a Toast shows except its × handler, which the provider owns. */
export type ToastMessage = Omit<ToastProps, "onClose">;

/** How long a toast stays before it hides itself. */
const TOAST_MS = 5000;

const ToastContext = createContext<((toast: ToastMessage) => void) | null>(null);

/**
 * Show a toast from anywhere inside <ToastProvider>:
 *
 *   const showToast = useToast();
 *   showToast({ tone: "success", title: "Asset saved successfully" });
 */
export function useToast(): (toast: ToastMessage) => void {
  const showToast = useContext(ToastContext);
  if (!showToast) throw new Error("useToast() must be used inside <ToastProvider>.");
  return showToast;
}

/**
 * Holds the one toast on screen. It sits in the (app) layout, which stays put
 * while pages change, so a toast shown on /assets/new is still visible after
 * moving to /dashboard. Bottom of the screen on mobile (N02 3488:171), bottom
 * right on desktop. A new toast replaces the old one.
 */
export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Hide it after TOAST_MS. Showing another toast restarts the timer.
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), TOAST_MS);
    return () => clearTimeout(timer);
  }, [toast]);

  return (
    <ToastContext.Provider value={setToast}>
      {children}
      {toast && (
        <div className="fixed inset-x-4 bottom-4 z-50 md:inset-x-auto md:right-8 md:bottom-8 md:w-[400px]">
          <Toast {...toast} onClose={() => setToast(null)} />
        </div>
      )}
    </ToastContext.Provider>
  );
}
