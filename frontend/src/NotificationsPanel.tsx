import { useEffect, useState } from "react";
import { Alert, Button, Checkbox, Group, Modal, NumberInput, Pagination, Paper, Select, Stack, Table, Text, Textarea, TextInput, Title } from "@mantine/core";
import { api } from "./api";
import { NotificationPreview, type NotificationBody } from "./NotificationPreview";
import { closeTestIntent, ensureTestIntent, readTestIntent, testReceiptMatches, testTerminal, type NotificationReceipt, type TestIntent } from "./notification-intent";
import { dateTime } from "./processTypes";
import type { CertificateStatus } from "./CertificateNotice";
import { useOperations } from "./OperationsStatus";
import { stateColor, stateLabel, type Flag, type OperationState } from "./operations";

type Settings = { recipients: string[]; certificate_time: string; daily_time: string; weekly_time: string; weekly_day: number; errors_enabled: boolean; outages_enabled: boolean; daily_enabled: boolean; weekly_enabled: boolean; error_bundle_minutes: number; error_repeat_hours: number; outage_after_minutes: number; outage_repeat_hours: number };
type Config = { version: number; scope_key: string; settings: Settings; configured: boolean; can_edit: boolean; automatic_schedule_active: Flag; automatic_schedule_state: OperationState };
type History = { items: NotificationReceipt[]; total: number; page: number; page_size: number };
type Payload = { message: { subject: string; body: NotificationBody; toRecipients: { emailAddress: { address: string } }[] } };
type Result = { ok: boolean; persisted: boolean; receipt: NotificationReceipt | null; payload?: Payload };
export const notificationStates: Record<string, string> = { prepared: "Vorbereitet / wartet", sending: "Versand läuft / Abgleich erforderlich", accepted: "Angenommen (202), Zustellung nicht bestätigt", rejected: "Sicher abgewiesen", unknown: "Ausgang ungewiss · Einmalversuch verbraucht", obsolete: "Überholt" };
const kinds: Record<string, string> = { certificate: "Zertifikatswarnung", test: "Testmail", daily: "Tagesbericht", weekly: "Wochenbericht", errors: "Verarbeitungsfehler", outage: "Technischer Ausfall", recovery: "Erholung" };
export default function NotificationsPanel({ identity, readOnly, csrfToken }: { identity: string; readOnly: boolean; csrfToken: string }) {
  const schedule = useOperations().status?.jobs.notifications.state ?? "unknown";
  const [config, setConfig] = useState<Config | null>(null), [recipients, setRecipients] = useState("");
  const [history, setHistory] = useState<History | null>(null), [page, setPage] = useState(1);
  const [cert, setCert] = useState<CertificateStatus | null>(null), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [intent, setIntent] = useState<TestIntent | null>(null), [receipt, setReceipt] = useState<NotificationReceipt | null>(null);
  const [preview, setPreview] = useState<Payload | null>(null);
  const editable = !readOnly && config?.can_edit === true;
  async function load() {
    const [value, rows, certificate] = await Promise.all([api<Config>("/api/notifications/config"), api<History>("/api/notifications/history?page=" + page), api<CertificateStatus>("/api/notifications/certificate")]);
    setConfig(value); setRecipients(value.settings.recipients.join("\n")); setHistory(rows); setCert(certificate);
  }
  function confirm(current: TestIntent, value: Result) {
    if (!value.persisted || !value.receipt || !testReceiptMatches(current, value.receipt)) throw new Error("Ergebnis nicht abschließend prüfbar. Dieselbe Testanforderung über Status abgleichen.");
    setReceipt(value.receipt); return value.receipt;
  }
  async function status(current: TestIntent) {
    const value = await api<Result>("/api/notifications/test/status?" + new URLSearchParams({ request_id: current.payload.request_id, expected_version: String(current.payload.expected_version) }));
    if (value.receipt) confirm(current, value);
    else throw new Error("Für die ursprüngliche Anforderung liegt noch keine Quittung vor. Dieselbe Anforderung beibehalten und erneut abgleichen oder ihre Vorschau aufrufen.");
  }
  useEffect(() => {
    let active = true;
    void load().catch(e => { if (active) setError(e.message); });
    try { const old = readTestIntent(localStorage, identity); setIntent(old); if (old) void status(old).catch(e => { if (active) setError(e.message); }); }
    catch (e) { setError(e instanceof Error ? e.message : "Testanforderung nicht verfügbar."); }
    return () => { active = false; };
  }, [identity, page]);
  function update<K extends keyof Settings>(name: K, value: Settings[K]) { setConfig(current => current ? { ...current, settings: { ...current.settings, [name]: value } } : current); }
  async function inspect() {
    if (!editable || !config) return;
    setBusy(true); setError("");
    try {
      const current = ensureTestIntent(localStorage, identity, config.scope_key, config.version); setIntent(current);
      const value = await api<Result>("/api/notifications/test/preview", { method: "POST", body: JSON.stringify(current.payload) }, csrfToken);
      confirm(current, value); if (!value.payload) throw new Error("Vorschau nicht vollständig."); setPreview(value.payload);
    } catch (e) { setError(e instanceof Error ? e.message : "Vorschau nicht verfügbar."); }
    finally { setBusy(false); }
  }
  async function send() {
    if (!intent || !editable) return;
    setBusy(true); setError(""); setPreview(null);
    try { confirm(intent, await api<Result>("/api/notifications/test", { method: "POST", body: JSON.stringify(intent.payload) }, csrfToken)); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Ergebnis unklar. Ursprüngliche Anforderung abgleichen."); }
    finally { setBusy(false); }
  }
  return <Stack>
    {error && <Alert color="red" role="alert">{error}</Alert>}
    <Alert color={stateColor[schedule]}>Benachrichtigungen: {stateLabel[schedule]}. Details zum aktuellen Betriebsstatus stehen in der Übersicht. Eine Testmail wird nur über die ausdrückliche Testaktion ausgelöst.</Alert>
    {cert && <Paper withBorder p="lg"><Title order={2}>Graph-Anmeldezertifikat</Title><Text mt="xs">{cert.local.expires_at ? "Lokale Datei: Ablauf " + dateTime(cert.local.expires_at) + " · Restzeit " + Math.floor((cert.local.remaining_seconds || 0) / 3600) + " Stunden." : "Lokale Datei nicht prüfbar."}</Text><Text size="sm">{cert.warning ? "Gespeicherte Pflichtwarnung offen." : "Keine offene Pflichtwarnserie gespeichert."} {cert.proof ? "Letzter erfolgreicher Nachfolgernachweis: " + dateTime(cert.proof.at) + "." : "Kein erfolgreicher Nachfolgernachweis gespeichert."}</Text></Paper>}
    {config && <Paper withBorder p="xl"><form onSubmit={async e => {
      e.preventDefault(); if (!editable) return; setBusy(true); setError("");
      try { const value = await api<Config>("/api/notifications/config", { method: "PUT", body: JSON.stringify({ expected_version: config.version, settings: { ...config.settings, recipients: recipients.split(/\r?\n/).map(value => value.trim()).filter(Boolean) } }) }, csrfToken); setConfig(value); setRecipients(value.settings.recipients.join("\n")); }
      catch (e) { setError(e instanceof Error ? e.message : "Einstellungen nicht gespeichert."); } finally { setBusy(false); }
    }}><Title order={2}>Empfänger & Zeitpläne · Stand {config.version}</Title><Text size="sm" c="dimmed" mt="xs" mb="lg">Alle Termine in Europe/Berlin. Die tägliche Zertifikatswarnung ist verpflichtend.</Text>
      <fieldset disabled={!editable || busy} className="settings-fieldset"><Stack>
        <Textarea label="Empfänger (eine Adresse je Zeile, höchstens 10)" value={recipients} onChange={e => setRecipients(e.currentTarget.value)} minRows={3} autosize required />
        <div className="settings-grid"><TextInput type="time" label="Pflichtwarnung Zertifikat" value={config.settings.certificate_time} onChange={e => update("certificate_time", e.currentTarget.value)} required />
          <TextInput type="time" label="Tagesbericht um" value={config.settings.daily_time} onChange={e => update("daily_time", e.currentTarget.value)} required />
          <TextInput type="time" label="Wochenbericht um" value={config.settings.weekly_time} onChange={e => update("weekly_time", e.currentTarget.value)} required />
          <Select label="Wochentag" value={String(config.settings.weekly_day)} onChange={v => update("weekly_day", Number(v))} allowDeselect={false} data={["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"].map((label, value) => ({ label, value: String(value) }))} /></div>
        <Group>{([['errors_enabled', 'Verarbeitungsfehler'], ['outages_enabled', 'Ausfälle und Erholung'], ['daily_enabled', 'Tagesberichte'], ['weekly_enabled', 'Wochenberichte']] as const).map(([name, label]) => <Checkbox key={name} label={label} checked={config.settings[name]} onChange={e => update(name, e.currentTarget.checked)} />)}</Group>
        <div className="settings-grid">{([['error_bundle_minutes', 'Fehler bündeln (Minuten)', 15, 1440], ['error_repeat_hours', 'Fehler erneut frühestens nach (Stunden)', 24, 168], ['outage_after_minutes', 'Ausfall melden nach (Minuten)', 5, 1440], ['outage_repeat_hours', 'Ausfall erneut frühestens nach (Stunden)', 24, 168]] as const).map(([name, label, min, max]) => <NumberInput key={name} label={label} min={min} max={max} allowDecimal={false} value={config.settings[name]} onChange={v => update(name, Number(v))} />)}</div>
        {editable && <Group justify="flex-end"><Button type="submit" loading={busy}>Einstellungen speichern</Button></Group>}
      </Stack></fieldset>{!editable && <Text size="sm" c="dimmed" mt="md">Schreibgeschützt. Änderungen und Testaufträge erfordern Verwaltungsrecht.</Text>}
    </form></Paper>}
    <Paper withBorder p="xl"><Title order={2}>Testmail</Title><Text size="sm" mt="xs" mb="md">Die Vorschau zeigt den festen Text und die gespeicherten Empfänger. Erst „Einmal senden“ startet den Versand.</Text>
      {intent && <Text size="xs" mb="sm">Ursprüngliche Anforderung: {intent.payload.request_id} · Einstellungsstand {intent.payload.expected_version}</Text>}
      {receipt && <Alert color={receipt.state === "accepted" ? "green" : "yellow"} mb="md">{notificationStates[receipt.state] || receipt.state}</Alert>}
      <Group>{editable && (!receipt || !testTerminal(receipt)) && <Button variant="light" onClick={() => void inspect()} disabled={!config?.configured} loading={busy}>Vorschau der Testmail</Button>}
        {intent && <Button variant="default" loading={busy} onClick={async () => { setBusy(true); setError(""); try { await status(intent); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Status nicht verfügbar."); } finally { setBusy(false); } }}>Ursprüngliche Anforderung abgleichen</Button>}
        {editable && receipt && testTerminal(receipt) && <Button variant="subtle" disabled={busy} onClick={() => { try { closeTestIntent(localStorage, identity, receipt); setIntent(null); setReceipt(null); } catch (e) { setError(e instanceof Error ? e.message : "Abgleich fehlt."); } }}>Abgeglichene Anforderung abschließen</Button>}
      </Group>
    </Paper>
    <Paper withBorder p="xl"><Title order={2}>Versandverlauf</Title><Text size="sm" c="dimmed" mb="md">Annahme durch Graph ist keine Zustellbestätigung. Ungewisse Einmalversuche werden nicht erneut gesendet.</Text>
      {history ? <><Table.ScrollContainer minWidth={600}><Table><Table.Thead><Table.Tr><Table.Th>Erstellt</Table.Th><Table.Th>Art</Table.Th><Table.Th>Status</Table.Th><Table.Th>Versuche</Table.Th></Table.Tr></Table.Thead><Table.Tbody>{history.items.map(row => <Table.Tr key={row.slot_key}><Table.Td>{dateTime(row.created_at)}</Table.Td><Table.Td>{kinds[row.kind] || row.kind}</Table.Td><Table.Td>{notificationStates[row.state] || row.state}</Table.Td><Table.Td>{row.reservations}</Table.Td></Table.Tr>)}</Table.Tbody></Table></Table.ScrollContainer>{!history.items.length && <Text c="dimmed">Noch keine Versandabsichten protokolliert.</Text>}{history.total > history.page_size && <Pagination mt="md" value={page} total={Math.ceil(history.total / history.page_size)} onChange={setPage} />}</> : <Text>Verlauf nicht geladen.</Text>}
    </Paper>
    <Modal opened={!!preview} onClose={() => setPreview(null)} title="Feste Testmail · Vorschau" size="lg" centered>{preview && <Stack><Text fw={600}>{preview.message.subject}</Text><Text size="sm">An: {preview.message.toRecipients.map(row => row.emailAddress.address).join(", ")}</Text><NotificationPreview body={preview.message.body} /><Button disabled={busy || !editable || !!receipt && testTerminal(receipt)} onClick={() => void send()}>Einmal senden</Button></Stack>}</Modal>
  </Stack>;
}
