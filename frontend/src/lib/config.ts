/**
 * Client-visible configuration.
 *
 * `NEXT_PUBLIC_*` values are inlined by Next at build time, so they must be
 * referenced as literal `process.env.NEXT_PUBLIC_X` expressions — never looked
 * up dynamically. Set them in `frontend/.env.local` (see `.env.example`).
 */

const DEFAULT_API_URL = "http://localhost:8000";

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

/** Base URL of the FastAPI backend, e.g. `http://localhost:8000`. */
export const API_BASE_URL = stripTrailingSlash(
  process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL,
);

/** Amazon Cognito app client ID. Empty until auth is wired up. */
export const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";

/** AWS region of the Cognito user pool. Same default as the backend's `aws_region`. */
export const COGNITO_REGION = process.env.NEXT_PUBLIC_COGNITO_REGION || "ap-southeast-1";

if (!process.env.NEXT_PUBLIC_API_URL && process.env.NODE_ENV !== "production") {
  console.warn(
    `NEXT_PUBLIC_API_URL is not set — falling back to ${DEFAULT_API_URL}. ` +
      "Copy frontend/.env.example to frontend/.env.local to configure it.",
  );
}
