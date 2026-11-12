import Image from "next/image";
import type { ComponentPropsWithoutRef } from "react";

interface TextFieldProps extends ComponentPropsWithoutRef<"input"> {
  /** Ties the <label> to the <input>; must be unique on the page. */
  id: string;
  /** Visible label above the field. */
  label: string;
  /** Path to the icon shown inside the field, e.g. "/icons/mail.svg". */
  iconSrc: string;
}

/** Labelled input with a leading icon — the field style from Figma D02 (3337:44). */
export default function TextField({
  id,
  label,
  iconSrc,
  className,
  ...inputProps
}: TextFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className="text-[13px] font-semibold tracking-[-0.26px] text-foreground"
      >
        {label}
      </label>
      <div className="flex h-[54px] items-center gap-3 rounded-[10px] border border-border px-4 focus-within:border-brand md:h-[52px] md:rounded-lg">
        <Image src={iconSrc} alt="" width={20} height={20} />
        <input
          id={id}
          className={`min-w-0 flex-1 self-stretch text-[15px] tracking-[-0.3px] outline-none placeholder:text-muted ${className ?? ""}`}
          {...inputProps}
        />
      </div>
    </div>
  );
}
