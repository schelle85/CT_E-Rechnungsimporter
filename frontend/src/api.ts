export type User = {
  guid: string;
  dn: string;
  username: string;
  role: "admin" | "reader";
};
export type AuthState = {
  authenticated: boolean;
  user?: User;
  csrf_token: string;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
  csrf?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  const data = await response
    .json()
    .catch(() => ({ detail: "Antwort nicht verfügbar." }));
  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "/api/auth/login" &&
      path !== "/api/auth/session"
    )
      window.dispatchEvent(new Event("session-invalid"));
    throw new ApiError(
      response.status,
      data.detail || "Anfrage fehlgeschlagen.",
    );
  }
  return data as T;
}
