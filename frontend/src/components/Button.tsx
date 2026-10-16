import type { ComponentPropsWithoutRef } from "react";

type ButtonVariant = "primary" | "secondary";

interface ButtonProps extends ComponentPropsWithoutRef<"button"> {
  /** "primary" is the filled brand button; "secondary" is the quieter outline one. */
  variant?: ButtonVariant;
}

/** Shared by every variant: size, shape, type and the disabled look. */
const baseClasses =
  "flex h-14 w-full items-center justify-center gap-2.5 rounded-[10px] text-[17px] font-bold tracking-[-0.34px] disabled:cursor-not-allowed disabled:opacity-50 md:h-[54px] md:rounded-lg";

/** Colours only. The full-width brand button from Figma D02 (3337:44). */
const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-brand text-brand-foreground",
  secondary: "border border-border bg-surface text-foreground",
};

/** Full-width action button: Sign In, Confirm, Cancel and the like. */
export default function Button({
  variant = "primary",
  type = "button",
  className,
  ...buttonProps
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`${baseClasses} ${variantClasses[variant]} ${className ?? ""}`}
      {...buttonProps}
    />
  );
}
