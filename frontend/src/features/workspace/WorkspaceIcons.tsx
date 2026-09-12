/**
 * Workspace type icons — Figma D03 (nodes 3344:23 and 3344:44).
 *
 * Inlined rather than loaded from /public because the selected card flips the
 * icon from blue to white. `stroke="currentColor"` lets the parent decide,
 * which an <img> cannot do. Geometry is unchanged from the Figma export.
 */

const strokeProps = {
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

interface IconProps {
  className?: string;
}

export function PersonalIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true" className={className}>
      <path
        d="M20.5833 22.75V20.5833C20.5833 19.4341 20.1268 18.3319 19.3141 17.5192C18.5015 16.7065 17.3993 16.25 16.25 16.25H9.75C8.60073 16.25 7.49853 16.7065 6.68587 17.5192C5.87321 18.3319 5.41667 19.4341 5.41667 20.5833V22.75"
        {...strokeProps}
      />
      <path
        d="M13 11.9167C15.3932 11.9167 17.3333 9.97657 17.3333 7.58333C17.3333 5.1901 15.3932 3.25 13 3.25C10.6068 3.25 8.66667 5.1901 8.66667 7.58333C8.66667 9.97657 10.6068 11.9167 13 11.9167Z"
        {...strokeProps}
      />
    </svg>
  );
}

export function OrganizationIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true" className={className}>
      <path
        d="M6.5 23.8333V4.33333C6.5 3.7587 6.72827 3.2076 7.1346 2.80127C7.54093 2.39494 8.09203 2.16667 8.66667 2.16667H17.3333C17.908 2.16667 18.4591 2.39494 18.8654 2.80127C19.2717 3.2076 19.5 3.7587 19.5 4.33333V23.8333H6.5Z"
        {...strokeProps}
      />
      <path
        d="M6.5 13H4.33333C3.7587 13 3.2076 13.2283 2.80127 13.6346C2.39494 14.0409 2.16667 14.592 2.16667 15.1667V21.6667C2.16667 22.2413 2.39494 22.7924 2.80127 23.1987C3.2076 23.6051 3.7587 23.8333 4.33333 23.8333H6.5"
        {...strokeProps}
      />
      <path
        d="M19.5 9.75H21.6667C22.2413 9.75 22.7924 9.97827 23.1987 10.3846C23.6051 10.7909 23.8333 11.342 23.8333 11.9167V21.6667C23.8333 22.2413 23.6051 22.7924 23.1987 23.1987C22.7924 23.6051 22.2413 23.8333 21.6667 23.8333H19.5"
        {...strokeProps}
      />
      <path d="M10.8333 6.5H15.1667" {...strokeProps} />
      <path d="M10.8333 10.8333H15.1667" {...strokeProps} />
      <path d="M10.8333 15.1667H15.1667" {...strokeProps} />
    </svg>
  );
}
