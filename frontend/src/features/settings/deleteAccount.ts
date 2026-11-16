import { ApiError, api } from "@/lib/api";
import { COGNITO_CLIENT_ID } from "@/lib/config";
import { CognitoError, confirmPassword, deleteCognitoUser } from "@/features/auth/cognito";
import { signOut, signedInEmail } from "@/features/auth/session";

/**
 * Deletes the signed-in person's account, in this order:
 *
 *   1. Check the password with Cognito. This also gives the access token
 *      that step 3 needs; nothing has been deleted if the password is wrong.
 *   2. DELETE /me: our backend deletes their data. It refuses (409) while
 *      they still own an organization, and nothing is deleted then either.
 *   3. Cognito DeleteUser: removes the sign-in itself, so the same email can
 *      sign up again later.
 *
 * Then the browser forgets the session. Throws an Error whose message can go
 * straight on screen.
 */
export async function deleteAccount(password: string): Promise<void> {
  if (!COGNITO_CLIENT_ID) {
    // Local UI demo without Cognito: pretend, so the screen can be tried out.
    await new Promise((resolve) => setTimeout(resolve, 600));
    signOut();
    return;
  }

  const email = signedInEmail();
  if (!email) throw new Error("Your session has ended. Sign in again, then try once more.");

  let accessToken: string;
  try {
    accessToken = await confirmPassword(email, password);
  } catch (error) {
    if (error instanceof CognitoError && error.code === "NotAuthorizedException") {
      throw new Error("That password isn't right.");
    }
    throw new Error(error instanceof Error ? error.message : "Something went wrong. Please try again.");
  }

  try {
    await api.delete("/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const detail = (error.body as { detail?: unknown } | null)?.detail;
      throw new Error(typeof detail === "string" ? detail : "Delete the organizations you own first.");
    }
    throw new Error("Couldn't delete your account. Check your connection and try again.");
  }

  try {
    await deleteCognitoUser(accessToken);
  } catch {
    // The data is already gone, so this still counts as deleted. The sign-in
    // survives only in Cognito; signing in again starts a fresh, empty account.
  }
  signOut();
}
