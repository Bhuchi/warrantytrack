import Image from "next/image";

/**
 * Brand panel on the auth screens — Figma D02 (3337:3) and M02 (3382:6).
 *
 * Desktop: a full-height column down the left with the feature list.
 * Mobile: a short hero across the top; the features and copyright are dropped
 * because the sheet below needs the room.
 */

const FEATURES = [
  "OCR reads your invoice automatically",
  "Expiry alerts 30 days in advance",
  "Personal and organization workspaces",
];

interface BrandPanelProps {
  /** Large headline, e.g. "Welcome back." */
  title: string;
  /** Supporting sentence under the headline. */
  subtitle: string;
}

export default function BrandPanel({ title, subtitle }: BrandPanelProps) {
  return (
    <aside className="flex flex-col justify-between bg-brand px-6 pt-7 pb-11 text-brand-foreground md:w-[560px] md:shrink-0 md:px-14 md:py-16">
      <div className="flex flex-col gap-2.5 md:gap-10">
        <div className="flex items-center gap-2.5 md:gap-3.5">
          <Image
            src="/warranty-logo-white.svg"
            alt=""
            width={60}
            height={60}
            priority
            className="size-9 md:size-[60px]"
          />
          <span className="text-[20px] font-bold md:text-[28px]">
            WarrantyTrack
          </span>
        </div>

        <div className="flex flex-col gap-2 md:gap-[18px]">
          <h1 className="text-[32px] leading-10 font-bold tracking-[-0.64px] md:text-[46px] md:leading-[54px] md:tracking-[-0.92px]">
            {title}
          </h1>
          <p className="text-[14px] leading-[22px] tracking-[-0.28px] opacity-80 md:text-[18px] md:leading-[30px] md:tracking-[-0.36px]">
            {subtitle}
          </p>
        </div>

        <ul className="hidden flex-col gap-5 md:flex">
          {FEATURES.map((feature) => (
            <li key={feature} className="flex items-center gap-3.5">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-[14px] bg-white/16">
                <Image src="/icons/check.svg" alt="" width={16} height={16} />
              </span>
              <span className="text-[16px] leading-6 tracking-[-0.32px] opacity-90">
                {feature}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <p className="hidden text-[13px] tracking-[-0.26px] opacity-60 md:block">
        © 2026 WarrantyTrack · DES424 Cloud-based Application
      </p>
    </aside>
  );
}
