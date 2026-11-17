import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Group, Pagination, Paper, SimpleGrid, Stack, Switch, Table, Text, Title } from "@mantine/core";
import { api } from "./api";
import { dateTime } from "./processTypes";
import { closeRotationIntent, discardStaleRotationIntent, ensureRotationIntent, readRotationIntent, rotationIntentKey,
  rotationReceiptMatches, rotationReceiptPath, rotationTerminal, type RotationIntent } from "./rotation-intent";
import { rotationStates, type RotationConfiguration, type RotationHistory, type RotationReceipt, type RotationResult, type RotationStatus } from "./rotation";

const time = (v: number | null | undefined) => v ? dateTime(v) : "Nicht bestätigt";
const problem = (e: unknown) => e instanceof Error ? e.message : "Der Stand konnte nicht bestätigt werden. Bitte dieselbe Anforderung abgleichen.";
const fingerprint = (value: string) => <Text size="xs" ff="monospace" style={{ overflowWrap: "anywhere" }}>{value}</Text>;
const stateColor = (r: RotationReceipt) => r.state === "completed" ? r.error_code ? "yellow" : "green" :
  ["failed", "registration_rejected", "registration_unknown", "rollback_unknown", "cleanup_unknown"].includes(r.state) ? "yellow" : "blue";
function guidance(row: RotationReceipt) {
  if (["registration_unknown", "rollback_unknown", "cleanup_unknown"].includes(row.state)) return "Der Ausgang ist noch ungewiss. Die ursprüngliche Anforderung beibehalten und die Betreuung zum Abgleich hinzuziehen.";
  if (row.state === "registration_rejected") return "Die Registrierung wurde sicher abgewiesen. Erst die Ursache durch die Betreuung klären; ein weiterer Versuch benötigt eine neue ausdrückliche Anforderung.";
  if (row.state === "failed") return "Der Wechsel wurde mit dem alten Zertifikat beendet. Bitte vor einem neuen Versuch die Betreuung hinzuziehen.";
  if (row.state === "completed" && row.error_code) return "Der Wechsel ist beendet. Ein Hinweis bleibt offen; bitte die Betreuung zur verbleibenden Bereinigung hinzuziehen.";
  if (row.state === "overlap") return "Der neue Zugang ist bestätigt. Das Altzertifikat bleibt bis zur vorgesehenen Bereinigung erhalten.";
  return row.state === "completed" ? "Der Ablauf ist abgeschlossen." : "Der Betreiberablauf bearbeitet diese Anforderung. Status aktualisieren, bis ein bestätigtes Ergebnis vorliegt.";
}

export default function GraphCertificatePanel({ identity, readOnly, csrfToken }: { identity: string; readOnly: boolean; csrfToken: string }) {
  const [status, setStatus] = useState<RotationStatus | null>(null), [history, setHistory] = useState<RotationHistory | null>(null), [page, setPage] = useState(1);
  const [intent, setIntent] = useState<RotationIntent | null>(null), [receipt, setReceipt] = useState<RotationReceipt | null>(null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false), [storageFailed, setStorageFailed] = useState(false), [discardable, setDiscardable] = useState(false);
  const mounted = useRef(false), generation = useRef(0), working = useRef(false);
  const editable = !readOnly && status?.can_edit === true;
  const host = status?.host.available ? status.host : null;
  const local = status && "fingerprint" in status.local ? status.local : null;
  const operation = host?.operation;

  async function readReceipt(current: RotationIntent) {
    const value = await api<RotationResult>(rotationReceiptPath(current));
    if (value.receipt && !rotationReceiptMatches(current, value.receipt)) throw new Error("Die Antwort gehört nicht zur ursprünglichen Anforderung. Bitte die Betreuung zum Abgleich hinzuziehen.");
    return value.receipt;
  }
  async function refresh() {
    const run = ++generation.current;
    try {
      const [next, rows] = await Promise.all([api<RotationStatus>("/api/rotation/status"), api<RotationHistory>("/api/rotation/history?page=" + page)]);
      if (!mounted.current || run !== generation.current) return;
      setStatus(next); setHistory(rows);
      let current: RotationIntent | null;
      try { current = readRotationIntent(localStorage, identity); setStorageFailed(false); }
      catch (e) { setStorageFailed(true); throw e; }
      setIntent(current); setReceipt(null); setDiscardable(false);
      // Read after the current head, so a missing receipt cannot conceal a concurrent acceptance.
      const row = current ? await readReceipt(current) : null;
      if (!mounted.current || run !== generation.current) return;
      setReceipt(row);
      setDiscardable(!!current && row === null && next.scope_key === current.payload.scope_key && next.revision > current.payload.expected_revision);
    } catch (e) {
      if (mounted.current && run === generation.current) { setError(problem(e)); setStatus(null); }
    }
  }
  useEffect(() => {
    mounted.current = true; setStatus(null); setHistory(null); setIntent(null); setReceipt(null); setError("");
    void refresh();
    const timer = setInterval(() => { if (!working.current) void refresh(); }, 15000);
    const changed = (event: StorageEvent) => { if (event.key === null || event.key === rotationIntentKey(identity)) void refresh(); };
    window.addEventListener("storage", changed);
    return () => { mounted.current = false; generation.current++; clearInterval(timer); window.removeEventListener("storage", changed); };
  }, [identity, page]);

  async function act(task: () => Promise<void>) {
    if (working.current) return;
    working.current = true; setBusy(true); setError(""); generation.current++;
    try {
      if (!navigator.locks) throw new Error("Dieser Browser unterstützt den sicheren Abgleich zwischen Fenstern nicht. Bitte einen aktuellen Browser über HTTPS verwenden.");
      await navigator.locks.request(rotationIntentKey(identity), { mode: "exclusive", ifAvailable: true }, async lock => {
        if (!lock) throw new Error("Ein anderes Fenster bearbeitet gerade dieselbe Anforderung. Bitte danach den Status aktualisieren.");
        await task();
      });
    } catch (e) { if (mounted.current) setError(problem(e)); }
    finally { working.current = false; if (mounted.current) { setBusy(false); await refresh(); } }
  }
  async function send(current: RotationIntent) {
    const result = await api<RotationResult>("/api/rotation/request", { method: "POST", body: JSON.stringify(current.payload) }, csrfToken);
    if (!result.receipt || !rotationReceiptMatches(current, result.receipt)) throw new Error("Anforderung gesendet, Ergebnis nicht bestätigt. Bitte die ursprüngliche Anforderung abgleichen.");
  }
  async function start() {
    if (!editable || !status || !local?.valid) return;
    await act(async () => {
      if (readRotationIntent(localStorage, identity)) throw new Error("Eine ursprüngliche Anforderung ist bereits gespeichert. Bitte diese zuerst abgleichen.");
      const current = ensureRotationIntent(localStorage, identity, status.scope_key, status.revision, local.fingerprint);
      setIntent(current); await send(current);
    });
  }
  async function resend() {
    if (!editable) return;
    await act(async () => {
      const current = readRotationIntent(localStorage, identity);
      if (!current) throw new Error("Keine ursprüngliche Anforderung gespeichert.");
      const known = await readReceipt(current);
      if (!known) await send(current); // A known request already belongs to the Host flow; never restart it.
    });
  }
  async function close() {
    await act(async () => {
      const current = readRotationIntent(localStorage, identity), row = current && await readReceipt(current);
      if (!row) throw new Error("Ein abschließender Abgleich fehlt.");
      closeRotationIntent(localStorage, identity, row);
    });
  }
  async function changeEnabled(enabled: boolean) {
    if (!editable || !status) return;
    await act(async () => { await api<RotationConfiguration>("/api/rotation/config", { method: "PUT", body: JSON.stringify({
      scope_key: status.scope_key, expected_revision: status.revision, enabled }) }, csrfToken); });
  }

  return <Stack>
    <Group justify="space-between"><div><Title order={2}>Graph-Zertifikat</Title><Text size="sm" c="dimmed">Anmeldung am E-Mail-Postfach · Alle Zeiten in Europe/Berlin</Text></div>
      <Button variant="default" loading={busy} onClick={() => { setError(""); void refresh(); }}>Status aktualisieren</Button></Group>
    {error && <Alert color="red" title="Abgleich erforderlich" role="alert">{error}</Alert>}
    <Paper withBorder p="lg"><Stack gap="xs"><Group justify="space-between"><Title order={3}>Aktives Anmeldezertifikat</Title>
      {local && <Badge color={!local.valid || local.severity === "red" ? "red" : local.severity === "orange" ? "orange" : "green"}>{local.valid ? "Lokal gültig" : "Lokal nicht gültig"}</Badge>}</Group>
      {local ? <><Text>Ablauf: {time(local.expires_at)} · Restzeit: {Math.floor(local.remaining_seconds / 3600)} Stunden</Text>
        <Text size="sm" c="dimmed">Fingerabdruck (SHA-256)</Text>{fingerprint(local.fingerprint)}</> : <Text>Die lokale Zertifikatsdatei ist nicht bestätigt.</Text>}
      <Text size="sm" c="dimmed">Die lokale Gültigkeit allein bestätigt keine erfolgreiche Anmeldung. Das HTTPS-Zertifikat wird getrennt verwaltet.</Text>
    </Stack></Paper>
    <SimpleGrid cols={{ base: 1, md: 3 }}>
      <Paper withBorder p="lg"><Text size="sm" c="dimmed">Letzter Erneuerungsversuch</Text><Text fw={600}>{time(host?.last_attempt?.at)}</Text>
        {host?.last_attempt && <Text size="sm">{rotationStates[host.last_attempt.state]}</Text>}</Paper>
      <Paper withBorder p="lg"><Text size="sm" c="dimmed">Letzte erfolgreiche Anmeldung mit aktivem Zertifikat</Text><Text fw={600}>{time(status?.last_successful_check_at)}</Text></Paper>
      <Paper withBorder p="lg"><Text size="sm" c="dimmed">Letzte erfolgreiche Erneuerung</Text><Text fw={600}>{time(host?.last_renewal?.at)}</Text></Paper>
    </SimpleGrid>
    <Paper withBorder p="lg"><Stack gap="md"><Title order={3}>Automatische Erneuerung</Title>
      <Switch label="Automatische Erneuerung erlauben" description="Gespeicherte Einstellung; die Ausführung muss zusätzlich vom Betreiber bestätigt sein."
        checked={status?.enabled ?? false} disabled={!editable || busy} onChange={event => void changeEnabled(event.currentTarget.checked)} />
      <Text size="sm">Tägliche Prüfung um 03:35 Uhr, Erneuerung ab 30 Tagen Restlaufzeit. Alt und Neu bleiben höchstens sieben Tage parallel, begrenzt durch den Ablauf des alten Zertifikats.</Text>
      <Alert color={host?.timers.daily && host.timers.opportunity ? "blue" : "yellow"}>
        {host ? <>Tagesprüfung: {host.timers.daily ? "Zeitplan bestätigt" : "Zeitplan nicht aktiv bestätigt"}. Auftragsbearbeitung: {host.timers.opportunity ? "minütlich bestätigt" : "Zeitplan nicht aktiv bestätigt"}.</> : "Die Host-Zeitpläne sind nicht aktuell bestätigt."}
        <Text size="sm" mt="xs">Nächster vorgesehener Prüftermin: {time(host?.timers.next_check_at)}.</Text>
      </Alert>
      {host?.last_check && <Text size="sm">Letzte Betreiberprüfung: {time(host.last_check.at)} · {host.last_check.ok ? "erfolgreich" : "nicht erfolgreich, Betreuung hinzuziehen"}.</Text>}
      {!editable && <Text size="sm" c="dimmed">Schreibgeschützt. Änderungen und manuelle Erneuerungen erfordern Verwaltungsrecht.</Text>}
    </Stack></Paper>
    <Paper withBorder p="lg"><Stack gap="md"><Title order={3}>Erneuerung & Überlappung</Title>
      {status?.active ? <Alert color={stateColor(status.active)} title={rotationStates[status.active.state]}>{guidance(status.active)}</Alert> :
        <Text>{status ? "Keine offene Erneuerung gespeichert." : "Offene Erneuerung nicht bestätigt."}</Text>}
      {operation && <><Text size="sm">Bestätigtes Ziel: {operation.target === "new" ? "neues Zertifikat" : "altes Zertifikat / Rückkehr"}.</Text>
        <SimpleGrid cols={{ base: 1, md: 2 }}>{([['old', 'Altzertifikat'], ['new', 'Neues Zertifikat']] as const).map(([name, label]) => <Paper key={name} withBorder p="md"><Text fw={600}>{label}</Text>
          <Text size="sm">Ablauf: {time(operation[name].expires_at)}</Text>{fingerprint(operation[name].fingerprint)}</Paper>)}</SimpleGrid>
        {operation.cleanup_not_before && <Text size="sm">Bereinigung frühestens: {time(operation.cleanup_not_before)}. Vor dem Entfernen ist eine frische erfolgreiche Anmeldung erforderlich.</Text>}
        {operation.managed_old === false && <Alert color="yellow">Das Altzertifikat ist nicht als verwalteter Bestand bestätigt. Es bleibt erhalten; die Betreuung muss die Bereinigung klären.</Alert>}
        {operation.cleanup_phase === "completed" && <Text size="sm">Bereinigung abgeschlossen{operation.managed_old === false ? "; unverwalteter Altbestand bleibt erhalten" : ""}.</Text>}
      </>}
      <Text size="sm">„Jetzt erneuern“ legt einen Auftrag für denselben geprüften Betreiberablauf an. Der Klick allein bestätigt keinen Zertifikatswechsel.</Text>
      {editable && <Button w="fit-content" loading={busy} disabled={!local?.valid || !!intent || storageFailed || !!status?.active && status.active.state !== "registration_rejected"} onClick={() => void start()}>Jetzt erneuern</Button>}
      {intent && <Paper withBorder p="md"><Stack gap="sm"><Text fw={600}>Gespeicherte ursprüngliche Anforderung</Text><Text size="xs" style={{ overflowWrap: "anywhere" }}>{intent.payload.operation_id}</Text>
        <Text size="sm">{receipt ? rotationStates[receipt.state] : "Noch keine passende Annahme bestätigt. Diese Anforderung bleibt auch nach Neuanmeldung erhalten."}</Text>
        <Group><Button variant="default" disabled={busy} onClick={() => { setError(""); void refresh(); }}>Ursprüngliche Anforderung abgleichen</Button>
          {editable && !receipt && !discardable && <Button variant="light" disabled={busy || storageFailed} onClick={() => void resend()}>Ursprüngliche Anforderung erneut übermitteln</Button>}
          {receipt && rotationTerminal(receipt) && <Button variant="subtle" disabled={busy} onClick={() => void close()}>Abgeglichene Anforderung schließen</Button>}
          {discardable && <Button variant="subtle" disabled={busy} onClick={() => void act(() => discardStaleRotationIntent(localStorage, identity,
            () => api<RotationStatus>("/api/rotation/status"), readReceipt))}>Nicht angenommene, überholte Anforderung verwerfen</Button>}
        </Group></Stack></Paper>}
    </Stack></Paper>
    <Paper withBorder p="lg"><Title order={3} mb="md">Verlauf</Title>
      {history ? <><Table.ScrollContainer minWidth={650}><Table><Table.Thead><Table.Tr><Table.Th>Angefordert</Table.Th><Table.Th>Auslöser</Table.Th><Table.Th>Status</Table.Th><Table.Th>Zuletzt geändert</Table.Th></Table.Tr></Table.Thead>
        <Table.Tbody>{history.items.map(row => <Table.Tr key={row.operation_id}><Table.Td>{time(row.created_at)}</Table.Td><Table.Td>{row.trigger_kind === "manual" ? "Manuell" : "Automatisch"}</Table.Td>
          <Table.Td><Text size="sm">{rotationStates[row.state]}</Text>{row.error_code && <Text size="xs" c="orange">Hinweis offen · Betreuung hinzuziehen</Text>}</Table.Td><Table.Td>{time(row.updated_at)}</Table.Td></Table.Tr>)}</Table.Tbody>
      </Table></Table.ScrollContainer>{history.items.length === 0 && <Text c="dimmed">Noch keine Anforderungen gespeichert.</Text>}
        {history.total > history.page_size && <Pagination mt="md" value={page} total={Math.min(10000, Math.ceil(history.total / history.page_size))} onChange={setPage} />}</> : <Text>Verlauf nicht geladen.</Text>}
    </Paper>
  </Stack>;
}
