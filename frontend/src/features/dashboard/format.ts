/** Share of `part` in `total` as a whole percentage; 0 when there is nothing yet. */
export function percent(part: number, total: number): number {
  return total === 0 ? 0 : Math.round((part / total) * 100);
}

/**
 * "2026-05-19" to "19 May 2026", the date style used across the Figma frames.
 * The added time keeps the date from shifting a day in time zones behind UTC.
 */
export function formatDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
