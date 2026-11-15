import type { IntentStorage } from "./pending-intents";
export type TestIntent = { actor: string; scope_key: string; payload: { request_id: string; expected_version: number } };
export type NotificationReceipt = { slot_key: string; request_id: string | null; actor: string; scope_key: string; kind: string; config_version: number; payload_hash: string; state: string; reservations: number; http_status: number | null; created_at: number };
const key = (identity: string) => "importer.notification-test.v1." + identity.toLowerCase();
export function readTestIntent(storage: IntentStorage, identity: string): TestIntent | null {
  const raw = storage.getItem(key(identity)); if (!raw) return null;
  const value = JSON.parse(raw) as TestIntent;
  if (!value || value.actor !== "ad:" + identity.toLowerCase() || !/^[0-9a-f]{64}$/.test(value.scope_key) || !value.payload ||
      !/^[0-9a-f-]{36}$/.test(value.payload.request_id) || !Number.isSafeInteger(value.payload.expected_version) || value.payload.expected_version < 0 ||
      Object.keys(value.payload).sort().join() !== "expected_version,request_id") throw new Error("Ursprüngliche Testanforderung ist nicht sicher lesbar. Bitte die Betreuung zum Abgleich hinzuziehen.");
  return value;
}
export function ensureTestIntent(storage: IntentStorage, identity: string, scope: string, version: number, uuid = () => crypto.randomUUID()): TestIntent {
  const old = readTestIntent(storage, identity); if (old) return old;
  const value = { actor: "ad:" + identity.toLowerCase(), scope_key: scope, payload: { request_id: uuid(), expected_version: version } };
  storage.setItem(key(identity), JSON.stringify(value)); // Required before the first HTTP request.
  return value;
}
export function testReceiptMatches(intent: TestIntent, receipt: NotificationReceipt): boolean {
  return receipt.request_id === intent.payload.request_id && receipt.config_version === intent.payload.expected_version && receipt.scope_key === intent.scope_key &&
    receipt.actor === intent.actor && receipt.kind === "test" && /^[0-9a-f]{64}$/.test(receipt.slot_key) && /^[0-9a-f]{64}$/.test(receipt.payload_hash);
}
export function testTerminal(receipt: NotificationReceipt): boolean {
  return receipt.state === "accepted" && receipt.reservations === 1 && receipt.http_status === 202 || receipt.state === "unknown" && receipt.reservations === 1 || ["rejected", "obsolete"].includes(receipt.state);
}
export function closeTestIntent(storage: IntentStorage, identity: string, receipt: NotificationReceipt) {
  const intent = readTestIntent(storage, identity);
  if (!intent || !testReceiptMatches(intent, receipt) || !testTerminal(receipt)) throw new Error("Testanforderung ist noch nicht abschließend abgeglichen.");
  storage.removeItem(key(identity));
}
