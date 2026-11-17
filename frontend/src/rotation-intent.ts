import type { IntentStorage } from "./pending-intents";
import { isRotationReceipt, rotationHash, rotationUuid, type RotationReceipt, type RotationStatus } from "./rotation.ts";
export type RotationIntent = { actor: string; payload: { operation_id: string; scope_key: string; expected_revision: number; old_fingerprint: string } };
export const rotationIntentKey = (identity: string) => "importer.rotation.v1." + identity.toLowerCase();
const problem = () => new Error("Die ursprüngliche Anforderung ist nicht sicher abgleichbar. Bitte die Betreuung hinzuziehen.");
function valid(v: unknown, identity: string): v is RotationIntent {
  const value = v as RotationIntent | null, p = value?.payload;
  return !!value && /^[0-9a-f]{32}$/i.test(identity) && value.actor === "ad:" + identity.toLowerCase() && !!p &&
    Object.keys(value).sort().join() === "actor,payload" && Object.keys(p).sort().join() === "expected_revision,old_fingerprint,operation_id,scope_key" &&
    rotationUuid(p.operation_id) && rotationHash(p.scope_key) && rotationHash(p.old_fingerprint) && Number.isSafeInteger(p.expected_revision) && p.expected_revision >= 0;
}
export function readRotationIntent(storage: IntentStorage, identity: string): RotationIntent | null {
  const raw = storage.getItem(rotationIntentKey(identity)); if (raw === null) return null;
  let value: unknown; try { value = JSON.parse(raw); } catch { throw problem(); }
  if (!valid(value, identity)) throw problem();
  return value;
}
/** Caller holds the browser's exclusive cross-tab lock through the first POST. */
export function ensureRotationIntent(storage: IntentStorage, identity: string, scope: string, revision: number, fingerprint: string, uuid = () => crypto.randomUUID()): RotationIntent {
  const old = readRotationIntent(storage, identity); if (old) return old;
  const value = { actor: "ad:" + identity.toLowerCase(), payload: { operation_id: uuid(), scope_key: scope, expected_revision: revision, old_fingerprint: fingerprint } };
  if (!valid(value, identity)) throw problem();
  storage.setItem(rotationIntentKey(identity), JSON.stringify(value)); // Must succeed before any request can be sent.
  if (JSON.stringify(readRotationIntent(storage, identity)) !== JSON.stringify(value)) throw problem();
  return value;
}
export function rotationReceiptMatches(intent: RotationIntent, receipt: RotationReceipt): boolean {
  const p = intent.payload;
  return isRotationReceipt(receipt) && receipt.actor === intent.actor && receipt.trigger_kind === "manual" &&
    receipt.operation_id === p.operation_id && receipt.scope_key === p.scope_key && receipt.expected_revision === p.expected_revision && receipt.old_fingerprint === p.old_fingerprint;
}
export const rotationTerminal = (receipt: RotationReceipt) => ["completed", "failed", "registration_rejected"].includes(receipt.state);
export function closeRotationIntent(storage: IntentStorage, identity: string, receipt: RotationReceipt) {
  const current = readRotationIntent(storage, identity);
  if (!current || !rotationReceiptMatches(current, receipt) || !rotationTerminal(receipt)) throw problem();
  storage.removeItem(rotationIntentKey(identity));
}
export function rotationReceiptPath(intent: RotationIntent): string {
  const p = intent.payload;
  return "/api/rotation/request?" + new URLSearchParams({ operation_id: p.operation_id, scope_key: p.scope_key,
    expected_revision: String(p.expected_revision), old_fingerprint: p.old_fingerprint });
}
/** A later locked head revision, THEN a missing original receipt, proves it can no longer be accepted. */
export async function discardStaleRotationIntent(storage: IntentStorage, identity: string,
  readStatus: () => Promise<RotationStatus>, readReceipt: (intent: RotationIntent) => Promise<RotationReceipt | null>) {
  const current = readRotationIntent(storage, identity); if (!current) throw problem();
  const status = await readStatus();
  if (status.scope_key !== current.payload.scope_key || status.revision <= current.payload.expected_revision) throw problem();
  if (await readReceipt(current) !== null || JSON.stringify(readRotationIntent(storage, identity)) !== JSON.stringify(current)) throw problem();
  storage.removeItem(rotationIntentKey(identity));
}
