import { useEffect, useState } from "react";
import { Alert, Badge, Button, Group, Modal, Paper, Select, Stack, Text, Title } from "@mantine/core";
import { api, ApiError } from "./api";
import { type PendingIntent, readPending, queuePending, rejectPending, resolvePending, intentPath, receiptMatches } from "./pending-intents";
import { type ProcessDetail, type ProcessingSettings, StatusBadge, dateTime, labels, reasonText } from "./processTypes";

export default function ProcessDialog({ detail, initialAttachment, settings, canEdit, identity, csrfToken, onClose, onChanged }: {
  detail: ProcessDetail | null; initialAttachment: string | null; settings: ProcessingSettings | null; canEdit: boolean;
  identity: string; csrfToken: string; onClose: () => void; onChanged: () => Promise<void>;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [decision, setDecision] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const [pending, setPending] = useState<PendingIntent | null>(null);
  const [loadedKey, setLoadedKey] = useState("");
  const currentKey = identity + ":" + (detail?.id || "");
  useEffect(() => {
    setSelected(initialAttachment || detail?.attachments.find(a => a.can_correct)?.id || detail?.attachments[0]?.id || null);
    setDecision(null); setNotice("");
  }, [detail?.id, initialAttachment]);
  const row = detail?.attachments.find(a => a.id === selected) || detail?.attachments[0];
  useEffect(() => {
    setLoadedKey("");
    if (!detail) { setPending(null); return; }
    try { setPending(readPending(sessionStorage, identity, detail.id)); setLoadedKey(currentKey); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Ausstehende Anforderung ist nicht verfügbar."); }
  }, [identity, detail?.id, currentKey]);
  async function submitIntent(intent: PendingIntent) {
    if (!canEdit || busy) return;
    setBusy(true); setNotice("");
    try {
      const receipt = await api<Record<string, unknown>>(intentPath(intent), { method: "POST", body: JSON.stringify(intent.payload) }, csrfToken);
      if (!await receiptMatches(intent, receipt)) throw new Error("Die Antwort bestätigt die ursprüngliche Anforderung nicht eindeutig.");
      resolvePending(sessionStorage, identity, intent.messageId); setPending(null); setDecision(null);
      await onChanged(); setNotice(intent.kind === "approve" ? "Zuordnung bestätigt. Der Verarbeitungsstatus folgt den tatsächlichen Belegen." : "Technische Wiederholung im Protokoll bestätigt.");
    } catch (error) {
      if (error instanceof ApiError && [400, 409, 422].includes(error.status)) {
        try { setPending(rejectPending(sessionStorage, identity, intent)); } catch { /* Keep the original pending intent. */ }
      }
      setNotice(error instanceof Error ? error.message : "Die Antwort ist nicht bestätigt. Bitte die ursprüngliche Anforderung abgleichen.");
    } finally { setBusy(false); }
  }
  async function approve() {
    if (!detail || !row || !decision || !row.finding_key || !row.sha256 || busy || pending || loadedKey !== currentKey) return;
    try {
      const intent = queuePending(sessionStorage, identity, { kind: "approve", messageId: detail.id, targetId: row.id,
        payload: { expected_revision: detail.revision, finding_revision: row.finding_revision, finding_key: row.finding_key,
          source_sha256: row.sha256, decision, request_id: crypto.randomUUID() } });
      setPending(intent); await submitIntent(intent);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Anforderung kann nicht sicher gespeichert werden."); }
  }
  async function retry() {
    if (!detail || busy || pending || loadedKey !== currentKey) return;
    try {
      const intent = queuePending(sessionStorage, identity, { kind: "retry", messageId: detail.id, targetId: detail.id,
        payload: { expected_revision: detail.revision, request_id: crypto.randomUUID() } });
      setPending(intent); await submitIntent(intent);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Anforderung kann nicht sicher gespeichert werden."); }
  }
  async function closeRejected() {
    if (!pending?.rejected || busy) return;
    try { resolvePending(sessionStorage, identity, pending.messageId); setPending(null); await onChanged(); setNotice("Abgewiesene Anforderung geschlossen. Eine neue Aktion muss ausdrücklich gewählt werden."); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Anforderung konnte nicht geschlossen werden."); }
  }
  const url = row ? "/api/attachments/" + row.id + "/original" : "";
  const pdf = row?.current_finding?.format === "PDF" || row?.original_finding?.format === "PDF";
  return <Modal opened={!!detail} onClose={busy ? () => undefined : onClose} title="Vorgang und Original" size="95vw" centered closeButtonProps={{ "aria-label": "Vorgang schließen", disabled: busy }} closeOnClickOutside={!busy} closeOnEscape={!busy}>
    {detail && <Stack gap="md">
      <Group justify="space-between"><div><Title order={2} size="h3">{row?.name || "Vorgang"}</Title><Text size="sm" c="dimmed">Eingang {dateTime(detail.received_at)} · {detail.attachment_count} Anhänge</Text></div>
        <Group><StatusBadge value={detail.state} />{detail.archived && <Badge color="gray">Archiv · nur lesen</Badge>}</Group></Group>
      {notice && <Alert role="status" color="blue">{notice}</Alert>}
      <div className="original-layout">
        <div className="original-pane">
          {row?.can_read_original && settings?.preview_enabled ? <>
            <Group mb="sm"><Button component="a" href={url} target="_blank" rel="noopener" variant="light">In neuem Tab öffnen</Button>
              <Button component="a" href={url + "?download=true"} variant="subtle">Original herunterladen</Button></Group>
            {pdf ? <iframe key={row.id} className="original-frame" title={"Original: " + row.name} src={url + "#toolbar=1&navpanes=0"} />
              : <Paper withBorder className="original-empty"><Text>Dieses Format wird als Originaldatei zum Herunterladen bereitgestellt.</Text></Paper>}
            <Text size="xs" c="dimmed" mt="xs">Falls die Anzeige leer bleibt, öffnen Sie das Original in einem neuen Tab oder laden Sie es herunter. Eine geänderte oder fehlende Quelle wird nicht ersetzt.</Text>
          </> : <Paper withBorder className="original-empty"><Text>{settings && !settings.preview_enabled ? "Die Originalanzeige ist derzeit deaktiviert." : "Für diesen Anhang ist derzeit kein überprüfbares Original verfügbar."}</Text></Paper>}
        </div>
        <Stack gap="md" className="original-actions">
          {pending && <Paper withBorder p="md"><Stack gap="sm"><Text fw={600}>Ausstehende Bestätigung</Text>
            <Text size="sm">{pending.kind === "approve" ? "Zuordnung für " + (detail.attachments.find(a => a.id === pending.targetId)?.name || "den ursprünglichen Anhang") + ": " + (labels[pending.payload.decision] || pending.payload.decision) : "Technische Wiederholung"} · ursprüngliche Revision {pending.payload.expected_revision}</Text>
            <Text size="xs" c="dimmed">Ziel, Auswahl und Anfrage-ID bleiben bis zur bestätigten Antwort erhalten. Neu laden erzeugt keinen neuen Auftrag.</Text>
            {canEdit && <Button variant="light" onClick={() => submitIntent(pending)} loading={busy}>Ursprüngliche Anforderung abgleichen</Button>}
            {canEdit && pending.rejected && <Button variant="subtle" onClick={closeRejected} disabled={busy}>Abgewiesene Anforderung schließen</Button>}
          </Stack></Paper>}
          <div><Text fw={600} mb="xs">Anhänge dieses Vorgangs</Text><Stack gap={6}>{detail.attachments.map(a =>
            <button className={a.id === row?.id ? "attachment-choice selected" : "attachment-choice"} key={a.id} disabled={busy}
              onClick={() => { setSelected(a.id); setDecision(null); setNotice(""); }} aria-label={"Anhang " + a.name + " anzeigen"}>
              <Text size="sm" fw={600}>{a.name}</Text><StatusBadge value={a.status} />
            </button>)}</Stack></div>
          {row && <>
            <Paper withBorder p="md"><Text fw={600}>Befund</Text><Text size="sm" mt={6}>{reasonText(row.current_finding)}</Text>
              <Text size="sm" mt="xs">Zuordnung: {row.category || (row.approval ? labels[row.approval.decision] || row.approval.decision : "Offen")}</Text>
              <Text size="sm">Ablage: {row.storage_state ? labels[row.storage_state] || row.storage_state : "Noch kein bestätigter Ablagebeleg"}</Text>
              {row.storage_target && <Text size="xs" className="break-text" mt="xs">{row.storage_target}</Text>}
              {row.storage_state === "duplicate" && <Text size="sm" c="dimmed">Der Dublettenbeleg verweist auf eine bereits bestätigte Ablage.</Text>}
            </Paper>
            {row.approval && <Paper withBorder p="md"><Group justify="space-between"><Text fw={600}>Freigabe</Text><StatusBadge value={row.approval.state} /></Group>
              <Text size="sm" mt="xs">{labels[row.approval.decision] || row.approval.decision}</Text><Text size="xs" c="dimmed">{row.approval.actor} · {dateTime(row.approval.approved_at)}</Text></Paper>}
            {canEdit && row.can_correct && !detail.archived && !pending && loadedKey === currentKey ? <Paper withBorder p="md"><Stack gap="sm"><Text fw={600}>Diesen Anhang zuordnen</Text>
              <Select label="Zuordnung" placeholder="Bitte ausdrücklich auswählen" value={decision} onChange={setDecision} disabled={busy}
                data={[{ value: "PDF", label: "PDF-Rechnung" }, { value: "Zahlungsavis", label: "Zahlungsavis" }, { value: "Mahnung", label: "Mahnung / Zahlungserinnerung" }, { value: "ignored", label: "Ignorieren" }]} />
              <Button onClick={approve} loading={busy} disabled={!decision}>Zuordnung freigeben</Button>
              <Text size="xs" c="dimmed">Die Freigabe gilt für diesen Anhang. Der ursprüngliche Befund bleibt erhalten.</Text>
            </Stack></Paper> : row.recognition_status === "unknown" && !row.approval && <Alert color="yellow">{!canEdit ? "Sie haben Leserechte. Die Zuordnung benötigt ein Verwaltungskonto." : detail.archived ? "Archivierte Vorgänge sind schreibgeschützt." : "Eine Freigabe ist für diesen aktuellen Zustand gesperrt. Bitte die Befunde und den Vorgangsstatus prüfen."}</Alert>}
            <details className="technical-details"><summary>Technische Angaben und Verlauf</summary><Stack gap="xs" mt="sm">
              <Text size="xs" className="break-text">Vorgang: {detail.id}</Text><Text size="xs" className="break-text">Anhang: {row.id}</Text>
              <Text size="xs" className="break-text">SHA-256: {row.sha256 || "Noch nicht ermittelt"}</Text>
              <Text size="xs">Größe: {row.byte_size === null ? "Unbekannt" : row.byte_size.toLocaleString("de-DE") + " Bytes"}</Text>
              <Text size="xs">Erstbefund: {row.original_finding?.reason || "Ausstehend"} · Regel {row.original_finding?.rule_version || "Quellprüfung"}</Text>
              <Text size="xs">Aktueller Befund: {row.current_finding?.reason || "Ausstehend"} · Generation {row.finding_revision}</Text>
              {(row.error_code || detail.error_code) && <Text size="xs">Fehler: {row.error_code || detail.error_code}</Text>}
              {row.storage_receipt && <Text size="xs">Dateibeleg: {labels[row.storage_receipt.state] || row.storage_receipt.state} · {row.storage_receipt.publication_attempts} Veröffentlichungsversuch(e)</Text>}
              <Text size="xs">Mailabschluss: {detail.mail_action_confirmed ? "Bestätigt" : "Noch nicht bestätigt"} · Revision {detail.revision}</Text>
              {detail.finding_history.filter(f => f.attachment_id === row.id).map((f, i) => <Text key={i} size="xs">Befund {f.revision}: {f.finding.reason}{f.recorded_at ? " · " + dateTime(f.recorded_at) : " · Bestandsbeleg"}</Text>)}
            </Stack></details>
          </>}
          {detail.retry_requests.map(r => <Paper key={r.request_key} withBorder p="sm"><Text size="sm">Technische Wiederholung: {labels[r.state] || r.state}</Text><Text size="xs" c="dimmed">{r.actor} · {dateTime(r.requested_at)}</Text></Paper>)}
          {canEdit && detail.can_retry && !detail.archived && !pending && loadedKey === currentKey && <Button color="orange" variant="light" onClick={retry} loading={busy}>Technische Wiederholung freigeben</Button>}
        </Stack>
      </div>
    </Stack>}
  </Modal>;
}