import type { ComponentType } from "react";

/** One card. `T` is the step's own set of ids, e.g. "upload" | "photo" | "manual". */
export interface MethodOption<T extends string> {
  id: T;
  /** Mobile label, e.g. "Upload". */
  label: string;
  /** Desktop label, e.g. "Upload File". */
  desktopLabel: string;
  /** Desktop only, under the label. */
  description: string;
  Icon: ComponentType<{ className?: string }>;
}

interface MethodCardsProps<T extends string> {
  options: readonly MethodOption<T>[];
  /** The selected card. */
  value: T;
  onSelect: (id: T) => void;
}

/**
 * A row of tappable method cards: Upload / Photo / Manual on step 1 (M06
 * 3382:513), Scan / Type on step 2 (3569:454). The selected one is blue.
 */
export default function MethodCards<T extends string>({ options, value, onSelect }: MethodCardsProps<T>) {
  return (
    <div className="flex gap-2.5 md:gap-4">
      {options.map(({ id, label, desktopLabel, description, Icon }) => {
        const selected = value === id;

        return (
          <button
            key={id}
            type="button"
            aria-pressed={selected}
            onClick={() => onSelect(id)}
            className={`flex flex-1 flex-col items-center gap-2 rounded-xl py-3.5 md:items-start md:gap-2.5 md:px-[18px] md:py-4 ${
              selected ? "border-2 border-brand bg-brand-subtle" : "border border-border bg-surface"
            }`}
          >
            <span
              className={`flex size-[38px] items-center justify-center rounded-[10px] md:size-10 ${
                selected ? "bg-brand text-brand-foreground" : "bg-canvas text-muted"
              }`}
            >
              <Icon className="size-[19px] md:size-5" />
            </span>
            <span className={`text-[13px] font-bold tracking-[-0.26px] md:text-[15px] ${selected ? "text-brand" : "text-foreground"}`}>
              <span className="md:hidden">{label}</span>
              <span className="hidden md:inline">{desktopLabel}</span>
            </span>
            <span className="hidden text-left text-[12px] tracking-[-0.24px] text-muted md:block">{description}</span>
          </button>
        );
      })}
    </div>
  );
}
