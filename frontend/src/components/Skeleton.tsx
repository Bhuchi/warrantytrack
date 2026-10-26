import type { ComponentPropsWithoutRef } from "react";

type SkeletonProps = ComponentPropsWithoutRef<"div">;

/** Neutral loading placeholder; size and shape come from the caller's classes. */
export default function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`motion-safe:animate-pulse rounded-md bg-muted/15 ${className ?? ""}`}
      {...props}
    />
  );
}
