export type OperationState = "active" | "paused" | "degraded" | "unknown";
export type OperationResult = "ok" | "deferred" | "failed" | "unknown" | "none";
export type Flag = boolean | null;
export const jobNames = ["inbox", "corrections", "notifications", "tls"] as const;
export type JobName = typeof jobNames[number];
export type JobStatus = { configured: Flag; active: Flag; running: Flag; blocked: Flag; last_result: OperationResult; last_run_at: number | null; next_run_at: number | null; state: OperationState };
export type OperationsStatus = {
  schema_version: 1; state: OperationState; reason: string | null; checked_at: number; generated_at: number | null; expires_at: number | null;
  source_commit: string | null; deployment_id: string | null; instance_id: string | null; boot_id: string | null; timezone: "Europe/Berlin";
  startup: { configured: Flag; active: Flag; ready: Flag; database_ready: Flag; nginx_ready: Flag; last_result: OperationResult; last_run_at: number | null };
  jobs: Record<JobName, JobStatus>; mounts: { importer: Flag; tls_source: Flag }; draining: Flag; processing_running: Flag;
  automatic_schedule_active: Flag; automatic_schedule_state: OperationState;
};
type Row = Record<string, unknown>;
const object = (value: unknown): value is Row => value !== null && typeof value === "object" && !Array.isArray(value);
const keys = (value: Row, names: readonly string[]) => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
const integer = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const instant = (value: unknown) => value === null || integer(value) && value <= 8640000000000;
const flag = (value: unknown) => value === null || typeof value === "boolean";
const uuid = (value: unknown) => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const result = (value: unknown) => typeof value === "string" && ["ok", "deferred", "failed", "unknown", "none"].includes(value);
export function scheduleStateMatches(active: unknown, state: unknown) {
  return active === null ? state === "unknown" : active === false ? state === "paused" : active === true && (state === "active" || state === "degraded");
}
export function isOperationsStatus(value: unknown): value is OperationsStatus {
  if (!object(value) || !keys(value, ["schema_version", "state", "reason", "checked_at", "generated_at", "expires_at", "source_commit", "deployment_id", "instance_id", "boot_id", "timezone", "startup", "jobs", "mounts", "draining", "processing_running", "automatic_schedule_active", "automatic_schedule_state"]) ||
      value.schema_version !== 1 || value.timezone !== "Europe/Berlin" || !integer(value.checked_at) || !flag(value.draining) || !flag(value.processing_running)) return false;
  const start = value.startup, jobs = value.jobs, mounts = value.mounts;
  if (!object(start) || !keys(start, ["configured", "active", "ready", "database_ready", "nginx_ready", "last_result", "last_run_at"]) ||
      ![start.configured, start.active, start.ready, start.database_ready, start.nginx_ready].every(flag) || !result(start.last_result) || !instant(start.last_run_at) ||
      start.active === true && start.configured !== true || !object(jobs) || !keys(jobs, jobNames) ||
      !object(mounts) || !keys(mounts, ["importer", "tls_source"]) || !Object.values(mounts).every(flag)) return false;
  for (const name of jobNames) {
    const row = jobs[name];
    if (!object(row) || !keys(row, ["configured", "active", "running", "blocked", "last_result", "last_run_at", "next_run_at", "state"]) ||
        ![row.configured, row.active, row.running, row.blocked].every(flag) || !result(row.last_result) || !instant(row.last_run_at) || !instant(row.next_run_at) ||
        row.active === true && row.configured !== true || !scheduleStateMatches(row.active, row.state)) return false;
  }
  if (value.reason !== null) {
    if (typeof value.reason !== "string" || !["missing", "unreadable", "invalid", "unbound", "binding", "boot", "future", "stale"].includes(value.reason) || value.state !== "unknown" ||
        [value.generated_at, value.expires_at, value.source_commit, value.deployment_id, value.instance_id, value.boot_id, value.draining, value.processing_running, value.automatic_schedule_active].some(item => item !== null) ||
        value.automatic_schedule_state !== "unknown" || Object.entries(start).some(([key, item]) => item !== (key === "last_result" ? "unknown" : null)) || Object.values(mounts).some(item => item !== null)) return false;
    return jobNames.every(name => Object.entries(jobs[name] as Row).every(([key, item]) => item === (["state", "last_result"].includes(key) ? "unknown" : null)));
  }
  if (!integer(value.generated_at) || value.expires_at !== value.generated_at + 180 || value.generated_at > value.checked_at + 30 || value.generated_at < value.checked_at - 180 ||
      typeof value.source_commit !== "string" || !/^[0-9a-f]{40}$/.test(value.source_commit) || ![value.deployment_id, value.instance_id, value.boot_id].every(uuid) ||
      start.last_run_at !== null && Number(start.last_run_at) > value.generated_at + 30) return false;
  for (const name of jobNames) {
    const row = jobs[name] as Row;
    if (row.last_run_at !== null && Number(row.last_run_at) > value.generated_at + 30) return false;
    const required = [start.configured, start.active, value.draining === false, row.blocked === false,
      ...(name === "notifications" ? [start.database_ready] : name === "tls" ? [start.nginx_ready, mounts.tls_source] : [start.ready, mounts.importer])];
    const expected = row.active === null ? "unknown" : row.active === false ? "paused" : required.every(item => item === true) && !["failed", "unknown"].includes(String(row.last_result)) ? "active" : "degraded";
    if (row.state !== expected) return false;
  }
  const states = jobNames.map(name => (jobs[name] as Row).state);
  const overall = states.includes("unknown") ? "unknown" : states.every(state => state === "paused") ? "paused" : states.every(state => state === "active") ? "active" : "degraded";
  const notification = jobs.notifications as Row;
  return value.state === overall && value.automatic_schedule_active === notification.active && value.automatic_schedule_state === notification.state;
}
export const stateLabel: Record<OperationState, string> = { active: "Zeitplan aktiv", paused: "Zeitplan pausiert", degraded: "Aktiv mit Einschränkungen", unknown: "Nicht prüfbar" };
export const stateColor: Record<OperationState, string> = { active: "green", paused: "gray", degraded: "yellow", unknown: "gray" };
export const resultLabel: Record<OperationResult, string> = { ok: "Erfolgreich beendet", deferred: "Zurückgestellt", failed: "Fehlgeschlagen", unknown: "Ergebnis nicht prüfbar", none: "Noch kein Lauf belegt" };
export function freshnessDeadline(value: OperationsStatus, started: number, received: number) {
  return value.expires_at === null ? received : received + Math.max(0, (value.expires_at - value.checked_at) * 1000 - Math.max(0, received - started));
}
export function freshStatus(value: OperationsStatus | null, deadline: number, now: number) {
  return value !== null && now < deadline ? value : null;
}
