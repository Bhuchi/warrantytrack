import type { ReactNode } from "react";

interface EmptyStateProps {
  /** Short explanation of why this view has no content. */
  message: string;
  /** Optional next step, such as an add or create button. */
  action?: ReactNode;
  /** Optional heading above the message. */
  title?: string;
}

/** Shared empty view for list and detail screens. */
export default function EmptyState({
  message,
  action,
  title,
}: EmptyStateProps) {
  return (
    <section className="flex w-full flex-col items-center justify-center gap-3 rounded-xl border border-border bg-surface px-5 py-10 text-center sm:px-8">
      <div className="flex max-w-prose flex-col items-center gap-2">
        {title ? (
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
        ) : null}
        <p className="text-sm leading-6 text-muted">{message}</p>
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </section>
  );
}
