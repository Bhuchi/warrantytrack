import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import Skeleton from "@/components/Skeleton";

export default function StatePreviewPage() {
  return (
    <main className="min-h-screen bg-canvas px-4 py-8 text-foreground sm:px-8 md:px-12 md:py-12">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold md:text-3xl">Shared state preview</h1>
          <p className="text-sm text-muted md:text-base">
            Preview Skeleton, EmptyState and ErrorState at mobile and desktop widths.
          </p>
        </header>

        <section className="flex flex-col gap-4" aria-labelledby="skeleton-heading">
          <h2 id="skeleton-heading" className="text-lg font-semibold">Skeleton</h2>
          <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 md:p-8">
            <Skeleton className="h-7 w-2/3 md:w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-28 w-full md:w-2/3" />
          </div>
        </section>

        <section className="flex flex-col gap-4" aria-labelledby="empty-heading">
          <h2 id="empty-heading" className="text-lg font-semibold">EmptyState</h2>
          <EmptyState
            title="No assets yet"
            message="Add your first asset to keep its receipt and warranty details together."
            action={
              <button type="button" className="rounded-lg bg-brand px-5 py-3 text-sm font-semibold text-brand-foreground">
                Add an asset
              </button>
            }
          />
          <EmptyState message="There are no notifications to show." />
        </section>

        <section className="flex flex-col gap-4" aria-labelledby="error-heading">
          <h2 id="error-heading" className="text-lg font-semibold">ErrorState</h2>
          <ErrorState
            message="Unable to load assets. Please try again."
            action={
              <button type="button" className="rounded-lg border border-border bg-surface px-5 py-3 text-sm font-semibold text-brand">
                Retry
              </button>
            }
          />
        </section>
      </div>
    </main>
  );
}
