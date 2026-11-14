/** Complete tab-local intents; no credentials, CSRF tokens, raw files or Graph IDs. */
export type ApprovalPayload = { request_id: string; expected_revision: number; finding_revision: number; finding_key: string; source_sha256: string; decision: string };
export type RetryPayload = { request_id: string; expected_revision: number };
export type PendingIntent = { kind: "approve"; messageId: string; targetId: string; payload: ApprovalPayload; rejected?: boolean }
  | { kind: "retry"; messageId: string; targetId: string; payload: RetryPayload; rejected?: boolean };
export type IntentStorage = { getItem(key: string): string | null; setItem(key: string, value: string): void; removeItem(key: string): void };
const keyPattern = /^[0-9a-f]{64}$/;
function storageKey(identity: string, messageId: string) { return "importer.pending.v1." + identity + "." + messageId; }
function valid(value: unknown): value is PendingIntent {
  if (!value || typeof value !== "object") return false;
  const item = value as PendingIntent, p = item.payload;
  if (!keyPattern.test(item.messageId || "") || !keyPattern.test(item.targetId || "") || !p ||
    !/^[a-zA-Z0-9_-]{8,128}$/.test(p.request_id || "") || !Number.isSafeInteger(p.expected_revision) || p.expected_revision < 0) return false;
  if (item.kind === "retry") return item.targetId === item.messageId && Object.keys(p).sort().join() === "expected_revision,request_id";
  if (item.kind !== "approve") return false;
  const approval = item.payload;
  return Number.isSafeInteger(approval.finding_revision) && approval.finding_revision >= 0 &&
    keyPattern.test(approval.finding_key) && keyPattern.test(approval.source_sha256) && ["PDF", "Zahlungsavis", "Mahnung", "ignored"].includes(approval.decision) &&
    Object.keys(approval).sort().join() === "decision,expected_revision,finding_key,finding_revision,request_id,source_sha256";
}
export function readPending(storage: IntentStorage, identity: string, messageId: string): PendingIntent | null {
  const raw = storage.getItem(storageKey(identity, messageId));
  if (raw === null) return null;
  const value: unknown = JSON.parse(raw);
  if (!valid(value) || value.messageId !== messageId) throw new Error("Die gespeicherte ausstehende Anforderung ist nicht lesbar.");
  return value;
}
export function queuePending(storage: IntentStorage, identity: string, intent: PendingIntent): PendingIntent {
  const previous = readPending(storage, identity, intent.messageId);
  if (previous) return previous; // A new detail revision never replaces an unconfirmed intent.
  if (!valid(intent)) throw new Error("Anforderung kann nicht sicher gespeichert werden.");
  const raw = JSON.stringify(intent);
  storage.setItem(storageKey(identity, intent.messageId), raw);
  return JSON.parse(raw) as PendingIntent;
}
export function rejectPending(storage: IntentStorage, identity: string, intent: PendingIntent): PendingIntent {
  const marked = { ...intent, rejected: true };
  storage.setItem(storageKey(identity, intent.messageId), JSON.stringify(marked));
  return marked;
}
export function resolvePending(storage: IntentStorage, identity: string, messageId: string) {
  storage.removeItem(storageKey(identity, messageId));
}
export function intentPath(intent: PendingIntent) {
  return intent.kind === "approve" ? "/api/attachments/" + intent.targetId + "/approve" : "/api/processes/" + intent.messageId + "/retry";
}
export async function receiptMatches(intent: PendingIntent, receipt: Record<string, unknown>): Promise<boolean> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify([intent.targetId, intent.payload.request_id])));
  const expected = Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join("");
  return intent.kind === "approve" ? receipt.correction_key === expected && receipt.attachment_key === intent.targetId && receipt.decision === intent.payload.decision
    : receipt.request_key === expected && receipt.message_key === intent.messageId && receipt.expected_revision === intent.payload.expected_revision;
}