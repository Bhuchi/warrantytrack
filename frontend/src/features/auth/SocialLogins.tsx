/**
 * "or continue with" divider and provider buttons — Figma D02 (3337:65) and
 * M02 (3382:55). Mobile simplifies the Microsoft mark to a brand-blue "M";
 * desktop uses the four-square logo.
 */

const MICROSOFT_SQUARES = ["#f25022", "#7fba00", "#00a4ef", "#ffb900"];

export default function SocialLogins() {
  return (
    <div className="flex w-full flex-col gap-[18px] md:gap-[22px]">
      <div className="flex items-center gap-3.5">
        <span className="h-px flex-1 bg-border" />
        <span className="text-[13px] tracking-[-0.26px] text-muted">
          or continue with
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="flex gap-3.5">
        <button
          type="button"
          disabled
          title="Google sign-in is not configured"
          className="flex h-[54px] flex-1 items-center justify-center gap-2.5 rounded-[10px] border border-border md:h-[52px] md:rounded-lg"
        >
          <span className="text-[19px] font-bold text-[#4285f4] md:text-[20px]">
            G
          </span>
          <span className="text-[15px] font-semibold tracking-[-0.3px]">
            Google
          </span>
        </button>

        <button
          type="button"
          disabled
          title="Microsoft sign-in is not configured"
          className="flex h-[54px] flex-1 items-center justify-center gap-2.5 rounded-[10px] border border-border md:h-[52px] md:rounded-lg"
        >
          <span className="text-[19px] font-bold text-brand md:hidden">M</span>
          <span
            className="hidden size-[18px] grid-cols-2 gap-[2px] md:grid"
            aria-hidden="true"
          >
            {MICROSOFT_SQUARES.map((color) => (
              <span key={color} style={{ backgroundColor: color }} />
            ))}
          </span>
          <span className="text-[15px] font-semibold tracking-[-0.3px]">
            Microsoft
          </span>
        </button>
      </div>
    </div>
  );
}
