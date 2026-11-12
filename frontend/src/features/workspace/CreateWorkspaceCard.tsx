import Image from "next/image";

interface CreateWorkspaceCardProps {
  /** Opens the Create an organization modal. */
  onCreate: () => void;
}

/**
 * The dashed "Create an organization" card shown to a new user — Figma
 * 3640:18 (desktop) and 3640:344 (mobile). CLOUDAPPG5-132.
 *
 * The whole card is one button. Mobile shows a chevron like the other cards;
 * desktop shows a "Create organization" label styled as a button (a <span>,
 * because a button cannot sit inside another button).
 */
export default function CreateWorkspaceCard({ onCreate }: CreateWorkspaceCardProps) {
  return (
    <button
      type="button"
      onClick={onCreate}
      className="flex flex-col gap-4 rounded-2xl border-[1.5px] border-dashed border-brand bg-surface p-5 text-left md:min-w-[260px] md:max-w-[420px] md:flex-1 md:gap-[22px] md:self-stretch md:px-8 md:pt-8 md:pb-7"
    >
      <span className="flex w-full items-center gap-3.5 md:flex-wrap md:gap-y-[22px]">
        <span className="flex size-[50px] shrink-0 items-center justify-center rounded-[13px] bg-brand-subtle text-brand md:size-14 md:rounded-[14px]">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-6 md:size-[26px]">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
          </svg>
        </span>

        <span className="flex min-w-px flex-1 flex-col gap-1 md:order-last md:w-full md:flex-none md:gap-2">
          <span className="text-[19px] font-bold tracking-[-0.38px] text-foreground md:text-[24px] md:tracking-[-0.48px]">
            Create an organization
          </span>
          <span className="text-[13px] leading-[19px] tracking-[-0.26px] text-muted md:hidden">
            You&apos;ll be its owner and can invite your team.
          </span>
          <span className="hidden text-[15px] leading-6 tracking-[-0.3px] text-muted md:block">
            Set up a shared workspace for your company. You&apos;ll be its owner and can invite your team.
          </span>
        </span>

        <Image
          src="/icons/chevron-right.svg"
          alt=""
          width={20}
          height={20}
          className="size-5 shrink-0 md:hidden"
        />
      </span>

      <span className="mt-auto hidden h-[50px] w-full items-center justify-center rounded-lg border border-border text-[16px] font-bold tracking-[-0.32px] text-brand md:flex">
        Create organization
      </span>
    </button>
  );
}
