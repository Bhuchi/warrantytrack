import Image from "next/image";
import Link from "next/link";

/** Landing Page — Figma D01 (node 3312:3) and M01 (node 3399:171). */

// Mobile-only: the desktop hero has no feature list.
const FEATURES = [
  "OCR reads your invoice automatically",
  "Expiry alerts 30 days in advance",
  "Personal and organization workspaces",
];

export default function LandingPage() {
  return (
    <main className="relative flex-1 overflow-hidden">
      {/* Decorative line artwork behind the hero, desktop only. In Figma this is
          33 separate vector groups (node 3313:1481); flattened to one export. */}
      <Image
        src="/hero-decoration.png"
        alt=""
        width={1440}
        height={434}
        aria-hidden="true"
        className="pointer-events-none absolute top-[150px] left-0 hidden w-full md:block"
      />

      <div className="relative mx-auto flex max-w-[1440px] flex-col gap-5 px-6 pt-[26px] pb-[18px] md:flex-row md:items-start md:justify-between md:gap-8 md:px-8 md:pt-0 md:pb-[120px]">
        <div className="flex flex-col gap-5 md:max-w-[691px] md:gap-[60px] md:pt-[116px]">
          <div className="flex flex-col gap-5 text-brand md:gap-6">
            <h1 className="text-[32px] leading-10 font-bold tracking-[-0.64px] md:text-[64px] md:leading-normal md:tracking-[-1.28px]">
              Smart Warranty Management for Everyone
            </h1>
            <p className="text-[15px] leading-6 tracking-[-0.3px] md:text-[18px] md:leading-[30px] md:tracking-[-0.36px]">
              Store, track, and manage all your warranties in one secure place.
              Never miss an expiration or claim again.
            </p>
          </div>

          <Link
            href="/signup"
            className="flex h-14 w-full items-center justify-center gap-2.5 rounded-[10px] bg-brand text-[17px] font-bold tracking-[-0.34px] text-brand-foreground md:h-[60px] md:w-fit md:rounded-lg md:px-6 md:text-[22px] md:tracking-[-0.44px]"
          >
            Get Started
            <Image
              src="/icons/arrow-right-sm.svg"
              alt=""
              width={18}
              height={18}
              className="md:hidden"
            />
            <Image
              src="/icon-arrow-right-lg.svg"
              alt=""
              width={23}
              height={21}
              className="hidden md:block"
            />
          </Link>
        </div>

        <div className="h-[168px] w-full overflow-hidden rounded-xl md:mt-[108px] md:flex md:h-[456px] md:w-[685px] md:shrink-0 md:items-center md:justify-center md:rounded-none md:bg-brand-soft">
          <Image
            src="/hero-illustration.png"
            alt="People browsing and buying products online"
            width={655}
            height={397}
            priority
            className="size-full object-cover md:h-auto md:w-[655px] md:object-contain"
          />
        </div>

        <ul className="flex flex-col gap-3.5 md:hidden">
          {FEATURES.map((feature) => (
            <li key={feature} className="flex items-center gap-3">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-subtle">
                <Image
                  src="/icons/check-brand.svg"
                  alt=""
                  width={15}
                  height={15}
                />
              </span>
              <span className="text-[14px] leading-5 tracking-[-0.28px] text-foreground">
                {feature}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
