import type { ReactNode } from "react";

interface ErrorStateProps {
  /** User-facing explanation, including a surfaced ApiError message if present. */
  message: string;
  /** Optional recovery step, such as a retry button. */
  action?: ReactNode;
  /** Optional heading above the message. */
  title?: string;
}

/** Shared, accessible error view for list and detail screens. */
export default function ErrorState({
  message,
  action,
  title = "Something went wrong",
}: ErrorStateProps) {
  return (
    <section
      role="alert"
      className="flex w-full flex-col items-center justify-center gap-3 rounded-xl border border-border bg-surface px-5 py-10 text-center sm:px-8"
    >
      <div className="flex max-w-prose flex-col items-center gap-2">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="text-sm leading-6 text-muted">{message}</p>
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </section>
  );
}
