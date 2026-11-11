import { setAuthTokenProvider } from "@/lib/api";
import {
  WORKSPACE_COOKIE,
  WORKSPACE_ID_COOKIE,
  WORKSPACE_NAME_COOKIE,
} from "@/features/workspace/workspaces";

import { refreshTokens, type CognitoTokens } from "./cognito";

/**
 * Who is signed in, kept across page refreshes (CLOUDAPPG5-122).
 *
 * The tokens live in localStorage, so a refresh keeps you signed in. Any
 * script on the page can read localStorage, so a cross-site-scripting bug
 * could leak the token; an httpOnly cookie would need a backend login route
 * we do not have. The ID token only lasts an hour, which limits the damage.
 *
 * Importing this file registers getIdToken with lib/api, so every API request
 * carries "Authorization: Bearer <ID token>" without asking for it.
 */

const STORAGE_KEY = "warrantytrack.session";

/** Refresh this long before the ID token actually expires. */
const EXPIRY_MARGIN_MS = 60_000;

interface StoredSession {
  idToken: string;
  refreshToken: string;
  /** When idToken stops working, in milliseconds since 1970. */
  expiresAt: number;
  email: string;
}

function readSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

function writeSession(session: StoredSession | null): void {
  if (typeof window === "undefined") return;
  if (session) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  else window.localStorage.removeItem(STORAGE_KEY);
}

/** Call after a successful sign-in. */
export function saveSession(tokens: CognitoTokens, email: string): void {
  writeSession({
    idToken: tokens.idToken,
    refreshToken: tokens.refreshToken,
    expiresAt: Date.now() + tokens.expiresIn * 1000,
    email,
  });
}

/** True when there are tokens to use (they may still need a refresh). */
export function isSignedIn(): boolean {
  return readSession() !== null;
}

/** The signed-in email, for showing in the UI. */
export function signedInEmail(): string | null {
  return readSession()?.email ?? null;
}

/**
 * Name and email read from the ID token, for the top bar. A JWT is three
 * base64url parts; the middle one is the claims as JSON. Reading it is safe
 * for display only: the backend checks the signature, we never trust it here.
 */
export function signedInUser(): { email: string; name: string | null } | null {
  const session = readSession();
  if (!session) return null;
  try {
    const part = session.idToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    // atob gives raw bytes; TextDecoder turns them into text, so Thai names survive.
    const bytes = Uint8Array.from(atob(part), (char) => char.charCodeAt(0));
    const claims = JSON.parse(new TextDecoder().decode(bytes)) as { name?: string; email?: string };
    return { email: claims.email ?? session.email, name: claims.name ?? null };
  } catch {
    return { email: session.email, name: null };
  }
}

/**
 * Several requests can start at once with an expired token. They all wait for
 * the same refresh instead of each asking Cognito for a new token.
 */
let refreshing: Promise<string | null> | null = null;

/** The current ID token, refreshed first if it is about to expire. Null when signed out. */
export async function getIdToken(): Promise<string | null> {
  const session = readSession();
  if (!session) return null;
  if (Date.now() < session.expiresAt - EXPIRY_MARGIN_MS) return session.idToken;

  refreshing ??= refreshTokens(session.refreshToken)
    .then((tokens) => {
      saveSession(tokens, session.email);
      return tokens.idToken;
    })
    .catch(() => {
      // The refresh token expired or was revoked: the user must sign in again.
      signOut();
      return null;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** Forget the tokens and the chosen workspace. The caller sends the user to /login. */
export function signOut(): void {
  writeSession(null);
  if (typeof document !== "undefined") {
    for (const name of [WORKSPACE_COOKIE, WORKSPACE_ID_COOKIE, WORKSPACE_NAME_COOKIE]) {
      document.cookie = `${name}=; path=/; max-age=0`;
    }
  }
}

setAuthTokenProvider(getIdToken);
