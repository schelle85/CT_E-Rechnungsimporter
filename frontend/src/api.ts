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
export class ApiProtocolError extends Error {
  constructor() { super("Die Serverantwort ist unvollständig oder nicht überprüfbar. Bitte die ursprüngliche Anforderung erneut abgleichen."); this.name = "ApiProtocolError"; }
}
function responseShape(path: string, method: string, data: Record<string, unknown>) {
  const route = path.split("?")[0];
  const integer = (value: unknown, min = 0) => typeof value === "number" && Number.isSafeInteger(value) && value >= min;
  const key = (value: unknown) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  if (method === "GET" && ["/api/processes", "/api/unknown"].includes(route))
    return Array.isArray(data.items) && integer(data.total) && integer(data.page, 1) && integer(data.page_size, 1);
  if (method === "GET" && route === "/api/processes/stats")
    return ["messages", "attachments", "unknown_open", "duplicates", "stored", "errors", "approved"].every(name => integer(data[name]));
  if (method === "GET" && /^\/api\/processes\/[0-9a-f]{64}$/.test(route))
    return key(data.id) && Array.isArray(data.attachments) && Array.isArray(data.retry_requests) && Array.isArray(data.finding_history) && integer(data.revision) && typeof data.can_retry === "boolean";
  if (route === "/api/admin/processing")
    return integer(data.version, 1) && typeof data.preview_enabled === "boolean" && typeof data.retry_enabled === "boolean" && typeof data.can_edit === "boolean";
  const approval = /^\/api\/attachments\/([0-9a-f]{64})\/approve$/.exec(route);
  if (method === "POST" && approval) return key(data.correction_key) && data.attachment_key === approval[1] && typeof data.decision === "string" && typeof data.state === "string";
  const retry = /^\/api\/processes\/([0-9a-f]{64})\/retry$/.exec(route);
  if (method === "POST" && retry) return key(data.request_key) && data.message_key === retry[1] && integer(data.expected_revision) && typeof data.state === "string";
  return true;
}
export async function api<T>(path: string, options: RequestInit = {}, csrf?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(path, { ...options, headers, credentials: "same-origin", cache: "no-store" });
  if (response.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/session")
    window.dispatchEvent(new Event("session-invalid"));
  let value: unknown;
  try { value = await response.json(); }
  catch { if (response.ok) throw new ApiProtocolError(); }
  const object = value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  if (!response.ok) throw new ApiError(response.status, typeof object?.detail === "string" ? object.detail : "Antwort nicht verfügbar.");
  if (!object || !responseShape(path, (options.method || "GET").toUpperCase(), object)) throw new ApiProtocolError();
  return object as T;
}
