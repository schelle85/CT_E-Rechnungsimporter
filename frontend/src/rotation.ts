/** Public, read-only AP12 projection and immutable request receipts. */
export const rotationStates = {
  requested: "Anforderung wartet", prepared: "Nachfolger vorbereitet", registration_started: "Registrierung begonnen",
  registration_unknown: "Registrierung ungewiss – Abgleich erforderlich", registration_rejected: "Registrierung sicher abgewiesen",
  registered: "Nachfolger registriert", candidate_verified: "Nachfolger geprüft", adoption_prepared: "Übernahme vorbereitet",
  adopting: "Übernahme läuft", rollback_unknown: "Rückkehr ungewiss – Betreuung erforderlich", adopted: "Nachfolger übernommen",
  overlap: "Nachfolger aktiv · Überlappung läuft", cleanup_started: "Altzertifikat wird bereinigt",
  cleanup_unknown: "Bereinigung ungewiss – Abgleich erforderlich", completed: "Abgeschlossen", failed: "Mit altem Zertifikat beendet",
} as const;
export type RotationState = keyof typeof rotationStates;
export type RotationReceipt = { operation_id: string; scope_key: string; actor: string; trigger_kind: "manual" | "automatic";
  request_hash: string; expected_revision: number; old_fingerprint: string; state: RotationState; revision: number;
  error_code: string | null; created_at: number; updated_at: number };
export type RotationResult = { ok: true } & ({ persisted: true; receipt: RotationReceipt } | { persisted: false; receipt: null });
export type RotationHistory = { items: RotationReceipt[]; total: number; page: number; page_size: number };
type PublicCertificate = { fingerprint: string; expires_at: number };
type LocalCertificate = PublicCertificate & { not_before: number; valid: boolean; remaining_seconds: number; severity: "healthy" | "orange" | "red" };
export type RotationHost = { available: false; code: "rotation_status_unconfirmed" } | {
  available: true; schema_version: 1; source_commit: string; deployment_id: string; instance_id: string; scope_key: string; boot_id: string;
  observed_at: number; last_check: { at: number; ok: boolean; code: string | null } | null;
  last_attempt: { operation_id: string; at: number; state: RotationState; code: string | null } | null;
  last_renewal: { operation_id: string; at: number; fingerprint: string } | null;
  operation: { operation_id: string; phase: string; target: "old" | "new"; old: PublicCertificate; new: PublicCertificate;
    cleanup_phase: string | null; cleanup_not_before: number | null; managed_old: boolean | null } | null;
  timers: { daily: boolean; opportunity: boolean; next_check_at: number | null };
};
export type RotationStatus = { scope_key: string; revision: number; enabled: boolean; can_edit: boolean;
  local: LocalCertificate | { code: "notification_certificate_unavailable" }; last_successful_check_at: number | null;
  active: RotationReceipt | null; host: RotationHost; checked_at: number;
  schedule: { timezone: "Europe/Berlin"; daily_time: "03:35"; renew_before_days: 30; overlap_days: 7 } };
export type RotationConfiguration = Pick<RotationStatus, "scope_key" | "revision" | "enabled" | "can_edit">;

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const integer = (v: unknown, min = 0): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= min;
export const rotationHash = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
export const rotationUuid = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(v) && v !== "00000000-0000-0000-0000-000000000000";
const code = (v: unknown) => v === null || typeof v === "string" && /^[a-z][a-z0-9_]{0,63}$/.test(v);
const state = (v: unknown): v is RotationState => typeof v === "string" && Object.hasOwn(rotationStates, v);
const stamp = (v: unknown, latest: number): v is number => integer(v, 1) && v <= latest;
const certificate = (v: unknown): v is PublicCertificate & Record<string, unknown> => object(v) && rotationHash(v.fingerprint) && integer(v.expires_at, 1);
export function isRotationReceipt(v: unknown): v is RotationReceipt {
  return object(v) && rotationUuid(v.operation_id) && rotationHash(v.scope_key) &&
    typeof v.actor === "string" && /^(system|operator|ad:[0-9a-f]{32})$/.test(v.actor) &&
    ["manual", "automatic"].includes(String(v.trigger_kind)) && (v.trigger_kind !== "automatic" || v.actor === "system") &&
    rotationHash(v.request_hash) && integer(v.expected_revision) && rotationHash(v.old_fingerprint) && state(v.state) &&
    integer(v.revision) && code(v.error_code) && integer(v.created_at, 1) && integer(v.updated_at, v.created_at);
}
function host(v: unknown, scope: string, now: number): v is RotationHost {
  if (!object(v)) return false;
  if (v.available === false) return v.code === "rotation_status_unconfirmed";
  if (v.available !== true || v.schema_version !== 1 || typeof v.source_commit !== "string" || !/^[0-9a-f]{40}$/.test(v.source_commit) ||
      !rotationUuid(v.deployment_id) || !rotationUuid(v.instance_id) || !rotationUuid(v.boot_id) || v.scope_key !== scope ||
      !stamp(v.observed_at, now) || now - v.observed_at > 180) return false;
  const check = v.last_check, attempt = v.last_attempt, renewal = v.last_renewal, op = v.operation, timers = v.timers;
  if (check !== null && !(object(check) && stamp(check.at, v.observed_at) && typeof check.ok === "boolean" && code(check.code))) return false;
  if (attempt !== null && !(object(attempt) && rotationUuid(attempt.operation_id) && stamp(attempt.at, v.observed_at) && state(attempt.state) && code(attempt.code))) return false;
  if (renewal !== null && !(object(renewal) && rotationUuid(renewal.operation_id) && stamp(renewal.at, v.observed_at) && rotationHash(renewal.fingerprint))) return false;
  if (op !== null && !(object(op) && rotationUuid(op.operation_id) && ["prepared", "activation_started", "activated", "consumers_verified", "proof_started", "proof_unknown", "proof_verified", "committed", "rollback_unknown"].includes(String(op.phase)) &&
      ["old", "new"].includes(String(op.target)) && certificate(op.old) && certificate(op.new) &&
      (op.cleanup_phase === null || ["planned", "removal_started", "removal_unknown", "remote_absent", "unmanaged_retained", "local_pending", "completed"].includes(String(op.cleanup_phase))) &&
      (op.cleanup_not_before === null || integer(op.cleanup_not_before, 1)) && (op.managed_old === null || typeof op.managed_old === "boolean"))) return false;
  return object(timers) && typeof timers.daily === "boolean" && typeof timers.opportunity === "boolean" &&
    (timers.next_check_at === null || timers.daily && integer(timers.next_check_at, v.observed_at + 1) && timers.next_check_at <= v.observed_at + 172800);
}
export function rotationResponseShape(route: string, method: string, data: Record<string, unknown>): boolean {
  if (route === "/api/rotation/request") return ["GET", "POST"].includes(method) && data.ok === true &&
    (method === "GET" && data.persisted === false && data.receipt === null || data.persisted === true && isRotationReceipt(data.receipt));
  if (route === "/api/rotation/history") return method === "GET" && Array.isArray(data.items) && data.items.every(isRotationReceipt) &&
    integer(data.total, data.items.length) && integer(data.page, 1) && data.page <= 10000 && data.page_size === 20 && data.items.length <= 20;
  if (!rotationHash(data.scope_key) || !integer(data.revision) || typeof data.enabled !== "boolean" || typeof data.can_edit !== "boolean") return false;
  if (route === "/api/rotation/config") return method === "PUT";
  if (route !== "/api/rotation/status" || method !== "GET" || !integer(data.checked_at, 1)) return false;
  const local = data.local, schedule = data.schedule;
  return object(local) && (local.code === "notification_certificate_unavailable" || certificate(local) && integer(local.not_before, 1) &&
      typeof local.valid === "boolean" && typeof local.remaining_seconds === "number" && Number.isSafeInteger(local.remaining_seconds) &&
      ["healthy", "orange", "red"].includes(String(local.severity))) &&
    (data.last_successful_check_at === null || stamp(data.last_successful_check_at, data.checked_at)) &&
    (data.active === null || isRotationReceipt(data.active) && data.active.scope_key === data.scope_key) &&
    host(data.host, data.scope_key, data.checked_at) && object(schedule) && schedule.timezone === "Europe/Berlin" &&
    schedule.daily_time === "03:35" && schedule.renew_before_days === 30 && schedule.overlap_days === 7;
}
