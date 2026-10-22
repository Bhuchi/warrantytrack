/** Share of `part` in `total` as a whole percentage; 0 when there is nothing yet. */
export function percent(part: number, total: number): number {
  return total === 0 ? 0 : Math.round((part / total) * 100);
}
