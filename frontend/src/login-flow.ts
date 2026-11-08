import type { AuthState } from "./api";

type Credentials = { username: string; password: string };
type LoginClient = {
  login: (credentials: Credentials, csrf: string) => Promise<AuthState>;
  session: () => Promise<AuthState>;
};
export const CHALLENGE_RENEWED =
  "Voranmeldung abgelaufen oder geändert. Bitte Kennwort erneut eingeben und anmelden.";

export async function attemptLogin(
  client: LoginClient,
  credentials: Credentials,
  csrf: string,
  invalidateChallenge: () => void,
): Promise<{ state: AuthState; notice: string }> {
  try {
    return { state: await client.login(credentials, csrf), notice: "" };
  } catch (error) {
    if (
      typeof error !== "object" || error === null ||
      !("status" in error) || error.status !== 403
    ) throw error;
    // Discard stale CSRF immediately. Fetch only a new challenge, never resend credentials.
    invalidateChallenge();
    return { state: await client.session(), notice: CHALLENGE_RENEWED };
  }
}
