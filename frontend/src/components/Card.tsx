import type { ComponentPropsWithoutRef } from "react";

/**
 * White bordered box shared by the Dashboard stat cards (3382:179), the
 * Dashboard panels (3382:214) and the Assets List rows (3382:375).
 *
 * Padding and layout differ between those, so Card leaves them out: pass them
 * in with className, e.g. <Card className="flex flex-col gap-2 px-3.5 py-[13px]">.
 */
export default function Card({
  className,
  ...divProps
}: ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={`overflow-hidden rounded-xl border border-border bg-surface ${className ?? ""}`}
      {...divProps}
    />
  );
}
