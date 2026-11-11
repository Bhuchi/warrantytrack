"use client";

import { Amplify } from "aws-amplify";
import {
  confirmResetPassword,
  confirmSignIn,
  confirmSignUp,
  fetchAuthSession,
  resendSignUpCode,
  resetPassword,
  signIn,
  signOut,
  signUp,
} from "aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "aws-amplify/auth/cognito";
import { defaultStorage, sessionStorage } from "aws-amplify/utils";

import { setAuthTokenProvider } from "@/lib/api";
import { COGNITO_CLIENT_ID, COGNITO_ENABLED, COGNITO_USER_POOL_ID } from "@/lib/config";
import { clearWorkspace } from "@/features/workspace/workspaces";

const REMEMBER_KEY = "warrantytrack_remember_session";
let configured = false;

export function configureAuth(): void {
  if (!COGNITO_ENABLED) throw new Error("Cognito pool and client IDs are required.");
  if (configured) return;
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: COGNITO_USER_POOL_ID,
        userPoolClientId: COGNITO_CLIENT_ID,
        loginWith: { email: true },
        signUpVerificationMethod: "code",
      },
    },
  });
  const remember = window.localStorage.getItem(REMEMBER_KEY) !== "false";
  cognitoUserPoolsTokenProvider.setKeyValueStorage(remember ? defaultStorage : sessionStorage);
  configured = true;
}

function setRememberSession(remember: boolean): void {
  window.localStorage.setItem(REMEMBER_KEY, String(remember));
  cognitoUserPoolsTokenProvider.setKeyValueStorage(remember ? defaultStorage : sessionStorage);
}

/** Amplify refreshes expired tokens when its refresh token is still valid. */
export async function getIdToken(): Promise<string | null> {
  configureAuth();
  try {
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() ?? null;
  } catch {
    return null;
  }
}

// The API always receives the ID token; workspace roles remain server-owned.
setAuthTokenProvider(getIdToken);

export async function signInWithEmail(email: string, password: string, remember: boolean) {
  configureAuth();
  setRememberSession(remember);
  return signIn({ username: email.trim().toLowerCase(), password });
}

export async function finishSignInChallenge(response: string) {
  configureAuth();
  return confirmSignIn({ challengeResponse: response });
}

export async function signUpWithEmail(name: string, email: string, password: string) {
  configureAuth();
  return signUp({
    username: email.trim().toLowerCase(),
    password,
    options: { userAttributes: { email: email.trim().toLowerCase(), name: name.trim() } },
  });
}

export async function confirmEmail(email: string, code: string) {
  configureAuth();
  return confirmSignUp({ username: email.trim().toLowerCase(), confirmationCode: code.trim() });
}

export async function resendConfirmationCode(email: string) {
  configureAuth();
  return resendSignUpCode({ username: email.trim().toLowerCase() });
}

export async function startPasswordReset(email: string) {
  configureAuth();
  return resetPassword({ username: email.trim().toLowerCase() });
}

export async function finishPasswordReset(email: string, code: string, password: string) {
  configureAuth();
  return confirmResetPassword({
    username: email.trim().toLowerCase(),
    confirmationCode: code.trim(),
    newPassword: password,
  });
}

export async function signOutSession(): Promise<void> {
  if (COGNITO_ENABLED) {
    configureAuth();
    await signOut();
  }
  clearWorkspace();
}

/** Display useful messages without exposing raw exception objects in the UI. */
export function authError(error: unknown): string {
  const name = error instanceof Error ? error.name : "";
  switch (name) {
    case "NotAuthorizedException": return "Incorrect email or password.";
    case "UserNotFoundException": return "Incorrect email or password.";
    case "UserNotConfirmedException": return "Confirm your email before signing in.";
    case "UsernameExistsException": return "An account with this email already exists.";
    case "CodeMismatchException": return "The confirmation code is incorrect.";
    case "ExpiredCodeException": return "The code has expired. Request a new one.";
    case "LimitExceededException": return "Too many attempts. Please try again later.";
    case "InvalidPasswordException": return "Choose a stronger password with upper and lower case letters, a number, and a symbol.";
    default: return error instanceof Error ? error.message : "Authentication failed. Please try again.";
  }
}
