import type { ReactNode } from "react";

/**
 * Auth screens are full-bleed: no marketing header or footer.
 *
 * Mobile (M02) stacks a blue hero above a white sheet; desktop (D02) puts the
 * blue panel down the left beside the card. Pages supply both halves.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-1 flex-col md:flex-row">
      {children}
    </div>
  );
}
