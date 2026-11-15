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
  const receipt = (value: unknown) => {
    const row = value as Record<string, unknown> | null;
    return !!row && key(row.slot_key) && key(row.scope_key) && typeof row.actor === "string" && typeof row.kind === "string" && integer(row.config_version) &&
      integer(row.reservations) && Number(row.reservations) <= 1 && integer(row.created_at) && ["prepared", "sending", "accepted", "rejected", "unknown", "obsolete"].includes(String(row.state)) &&
      (row.kind !== "test" || typeof row.request_id === "string" && key(row.payload_hash));
  };
  if (route === "/api/notifications/config") {
    const settings = data.settings as Record<string, unknown> | null;
    return integer(data.version) && key(data.scope_key) && typeof data.configured === "boolean" && typeof data.can_edit === "boolean" && data.automatic_schedule_active === false && !!settings && Array.isArray(settings.recipients);
  }
  if (method === "GET" && route === "/api/notifications/history")
    return Array.isArray(data.items) && data.items.every(receipt) && integer(data.total) && integer(data.page, 1) && integer(data.page_size, 1);
  if (["/api/notifications/test", "/api/notifications/test/preview", "/api/notifications/test/status"].includes(route)) {
    if (data.persisted === false) return data.ok === false && typeof data.code === "string";
    if (data.persisted !== true || typeof data.ok !== "boolean" || !(data.receipt === null && route.endsWith("/status") || receipt(data.receipt))) return false;
    if (!route.endsWith("/preview")) return true;
    const payload = data.payload as { message?: { subject?: unknown; body?: { content?: unknown }; toRecipients?: unknown[] } } | null;
    return !!payload?.message && typeof payload.message.subject === "string" && typeof payload.message.body?.content === "string" &&
      Array.isArray(payload.message.toRecipients) && payload.message.toRecipients.length >= 1 && payload.message.toRecipients.length <= 10 &&
      payload.message.toRecipients.every(value => typeof (value as { emailAddress?: { address?: unknown } })?.emailAddress?.address === "string");
  }
  if (method === "GET" && route === "/api/admin/reports") {
    const counts = data.counts as Record<string, unknown> | undefined;
    return data.synthetic === false && integer(data.start) && integer(data.end) && integer(data.as_of) && data.timezone === "Europe/Berlin" && !!counts &&
      ["messages", "attachments", "unknown_open", "stored_receipts", "duplicates", "attachment_errors", "blocked_messages", "E-Rechnung", "PDF", "Zahlungsavis", "Mahnung"].every(name => integer(counts[name]));
  }
  if (method === "GET" && route === "/api/notifications/certificate") {
    const certificate = (value: unknown) => {
      const row = value as Record<string, unknown> | null;
      return !!row && key(row.fingerprint) && integer(row.expires_at) && typeof row.remaining_seconds === "number" && Number.isSafeInteger(row.remaining_seconds) && ["healthy", "orange", "red"].includes(String(row.severity));
    };
    const local = data.local as Record<string, unknown> | null, proof = data.proof as Record<string, unknown> | null;
    return integer(data.checked_at) && !!local && (local.code === "notification_certificate_unavailable" || certificate(local) && typeof local.valid === "boolean") &&
      (data.warning === null || certificate(data.warning)) && (proof === null || !!proof && key(proof.fingerprint) && integer(proof.at));
  }
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
