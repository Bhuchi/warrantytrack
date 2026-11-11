import { COGNITO_CLIENT_ID, COGNITO_REGION } from "@/lib/config";

/**
 * The only file that talks to Amazon Cognito (CLOUDAPPG5-122).
 *
 * Cognito has a plain JSON API: every action is a POST to the same URL, and the
 * X-Amz-Target header names the action. The app client has no secret and
 * allows USER_PASSWORD_AUTH (infra/aws/identity.tf), so the browser can call it
 * directly with fetch; no AWS library is needed.
 *
 * This is not lib/api: that module is the door to our own backend. Cognito is
 * a different server, so it gets its own small door here.
 */

/** What a successful sign-in gives back. The backend only accepts the ID token. */
export interface CognitoTokens {
  idToken: string;
  refreshToken: string;
  /** Seconds until idToken expires (Cognito's default is 3600). */
  expiresIn: number;
}

/** Thrown when Cognito says no. `code` is Cognito's error name, e.g. "NotAuthorizedException". */
export class CognitoError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "CognitoError";
    this.code = code;
  }
}

/**
 * Cognito's own messages are written for developers. These are the ones a user
 * can actually hit on our screens, reworded. Anything else shows a generic line.
 */
const FRIENDLY_MESSAGES: Record<string, string> = {
  NotAuthorizedException: "Incorrect email or password.",
  UserNotConfirmedException: "Please confirm your email first. Check your inbox for the code.",
  UsernameExistsException: "An account with this email already exists.",
  InvalidPasswordException:
    "Password needs at least 8 characters, with upper and lower case letters, a number and a symbol.",
  CodeMismatchException: "That code is not right. Check the email and try again.",
  ExpiredCodeException: "That code has expired. Press Send a new code.",
  TooManyRequestsException: "Too many attempts. Wait a minute and try again.",
  LimitExceededException: "Too many attempts. Wait a minute and try again.",
};

/** Sends one action to Cognito and returns its JSON reply, or throws CognitoError. */
async function callCognito<T>(action: string, body: object): Promise<T> {
  if (!COGNITO_CLIENT_ID) {
    throw new CognitoError(
      "NotConfigured",
      "Sign-in is not set up. Add NEXT_PUBLIC_COGNITO_CLIENT_ID to frontend/.env.local.",
    );
  }

  let response: Response;
  try {
    response = await fetch(`https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
      },
      body: JSON.stringify({ ClientId: COGNITO_CLIENT_ID, ...body }),
    });
  } catch {
    throw new CognitoError("NetworkError", "Can't reach the sign-in service. Check your connection.");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // __type is sometimes "NotAuthorizedException", sometimes "com.amazonaws...#NotAuthorizedException".
    const code = String(data.__type ?? "UnknownError").split("#").pop()!;
    throw new CognitoError(code, FRIENDLY_MESSAGES[code] ?? "Something went wrong. Please try again.");
  }
  return data as T;
}

/** The part of InitiateAuth's reply we use. */
interface InitiateAuthReply {
  AuthenticationResult?: { IdToken: string; RefreshToken?: string; ExpiresIn: number };
  ChallengeName?: string;
}

/** Signs in with email and password. */
export async function signIn(email: string, password: string): Promise<CognitoTokens> {
  const reply = await callCognito<InitiateAuthReply>("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });

  // A "challenge" means Cognito wants one more step, e.g. a user created by an
  // admin without a permanent password. Our screens don't handle that.
  const result = reply.AuthenticationResult;
  if (!result?.RefreshToken) {
    throw new CognitoError(
      reply.ChallengeName ?? "UnknownError",
      "This account needs setting up by an admin before it can sign in.",
    );
  }
  return { idToken: result.IdToken, refreshToken: result.RefreshToken, expiresIn: result.ExpiresIn };
}

/** Swaps a refresh token for a new ID token. Cognito keeps the same refresh token. */
export async function refreshTokens(refreshToken: string): Promise<CognitoTokens> {
  const reply = await callCognito<InitiateAuthReply>("InitiateAuth", {
    AuthFlow: "REFRESH_TOKEN_AUTH",
    AuthParameters: { REFRESH_TOKEN: refreshToken },
  });
  const result = reply.AuthenticationResult;
  if (!result) throw new CognitoError("UnknownError", "Your session has ended. Please sign in again.");
  return { idToken: result.IdToken, refreshToken, expiresIn: result.ExpiresIn };
}

/** Creates the account. Cognito then emails a 6-digit code to confirm it. */
export async function signUp(email: string, password: string, name: string): Promise<void> {
  await callCognito("SignUp", {
    Username: email,
    Password: password,
    UserAttributes: [
      { Name: "email", Value: email },
      { Name: "name", Value: name },
    ],
  });
}

/** Confirms the account with the code from the email. After this, signIn works. */
export async function confirmSignUp(email: string, code: string): Promise<void> {
  await callCognito("ConfirmSignUp", { Username: email, ConfirmationCode: code });
}

/** Emails a fresh code, for an account that was created but never confirmed. */
export async function resendConfirmationCode(email: string): Promise<void> {
  await callCognito("ResendConfirmationCode", { Username: email });
}
