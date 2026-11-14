import { Badge } from "@mantine/core";
export type Finding = { status: string; category: string | null; reason: string; method?: string; format?: string; rule_version?: string };
export type Attachment = {
  id: string; message_id: string; name: string; byte_size: number | null; sha256: string | null;
  status: string; recognition_status: string | null; category: string | null;
  original_finding: Finding | null; current_finding: Finding | null; finding_key: string | null; finding_revision: number;
  can_correct: boolean; can_read_original: boolean; signature_exception: boolean;
  storage_state: string | null; storage_target: string | null; error_code: string | null;
  approval: null | { id: string; decision: string; actor: string; approved_at: number; state: string; applied_revision: number | null };
  storage_receipt: null | { id: string; state: string; target: string | null; duplicate_of: string | null; publication_attempts: number; updated_at: number };
};
export type Process = {
  id: string; received_at: string; created_at: number; updated_at: number; state: string; revision: number;
  completed_revision: number; archived: boolean; owner_active: boolean; attachment_count: number; unknown_open: number;
  duplicate_count: number; stored_count: number; failed_count: number; categories: string[]; names: string[];
  destination: string | null; mail_action_confirmed: boolean; error_code: string | null;
};
export type ProcessDetail = Process & {
  attachments: Attachment[]; can_retry: boolean;
  retry_requests: { request_key: string; state: string; actor: string; requested_at: number; applied_revision: number | null; error_code: string | null }[];
  finding_history: { attachment_id: string; revision: number; finding: Finding; recorded_at: number }[];
};
export type ProcessingSettings = { version: number; preview_enabled: boolean; retry_enabled: boolean; can_edit: boolean };
export type Stats = { messages: number; attachments: number; unknown_open: number; duplicates: number; stored: number; errors: number; approved: number };
export type PageResult<T> = { items: T[]; total: number; page: number; page_size: number };
export const labels: Record<string, string> = {
  registered: "Wartet", processing: "In Bearbeitung", closing: "Abschluss läuft", waiting_correction: "Unbekannt",
  done: "Abgeschlossen", failed: "Fehler", operator_required: "Klärung erforderlich", unknown: "Unbekannt",
  approved: "Freigegeben", processed: "Verarbeitet", requested: "Wiederholung freigegeben", waiting: "Wartet",
  stored: "Abgelegt", duplicate: "Dublette", ignored: "Ignorieren", recognized: "Erkannt",
};
export function StatusBadge({ value }: { value: string }) {
  return <Badge radius="sm" variant="light" color={value === "failed" || value === "operator_required" ? "red" :
    value === "unknown" || value === "waiting_correction" ? "yellow" : ["done", "processed", "stored"].includes(value) ? "teal" : "blue"}>
    {labels[value] || value}
  </Badge>;
}
export function dateTime(value: string | number) {
  return new Date(typeof value === "number" ? value * 1000 : value).toLocaleString("de-DE", { timeZone: "Europe/Berlin", dateStyle: "medium", timeStyle: "short" });
}
export function reasonText(value: Finding | null) {
  if (!value) return "Ein aktueller Befund steht noch aus.";
  if (value.status === "failed") return "Der technische Abruf oder die Prüfung ist fehlgeschlagen.";
  if (value.status === "unknown") return ["ambiguous_pdf", "ambiguous_invoice", "ambiguous_payment_advice", "ambiguous_reminder", "ambiguous_mixed_document"].includes(value.reason)
    ? "Die Dokumentart ist nicht eindeutig. Bitte den Anhang prüfen."
    : "Der Befund enthält einen Struktur- oder Formatkonflikt. Eine manuelle Zuordnung ist gesperrt.";
  return value.status === "recognized" ? "Die Dokumentart wurde erkannt." : "Der Anhang wurde gemäß dem protokollierten Befund ausgenommen.";
}