import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Alert, Badge, Group, Paper, Table, Text, Title } from "@mantine/core";
import { api } from "./api";
import { freshStatus, freshnessDeadline, jobNames, resultLabel, stateColor, stateLabel, type Flag, type OperationsStatus } from "./operations";
import { dateTime } from "./processTypes";

const Context = createContext<{ status: OperationsStatus | null; refresh: () => Promise<void> }>({ status: null, refresh: async () => {} });
export const useOperations = () => useContext(Context);
export function OperationsProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<OperationsStatus | null>(null);
  const latest = useRef<{ value: OperationsStatus | null; deadline: number }>({ value: null, deadline: 0 });
  const pending = useRef<AbortController | null>(null);
  const mounted = useRef(false);
  const refresh = useCallback(async () => {
    if (pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    const started = performance.now(), timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const value = await api<OperationsStatus>("/api/operations/status", { signal: controller.signal });
      if (mounted.current && pending.current === controller) {
        const received = performance.now(), deadline = freshnessDeadline(value, started, received);
        latest.current = { value, deadline }; setStatus(freshStatus(value, deadline, received));
      }
    } catch {
      if (mounted.current && pending.current === controller) { latest.current = { value: null, deadline: 0 }; setStatus(null); }
    } finally { clearTimeout(timeout); if (pending.current === controller) pending.current = null; }
  }, []);
  useEffect(() => {
    mounted.current = true;
    const expire = () => { const current = latest.current; if (!freshStatus(current.value, current.deadline, performance.now())) setStatus(null); };
    const focus = () => { expire(); void refresh(); };
    void refresh();
    const poll = setInterval(() => void refresh(), 30000), expiry = setInterval(expire, 1000);
    window.addEventListener("focus", focus); document.addEventListener("visibilitychange", focus);
    return () => { mounted.current = false; pending.current?.abort(); pending.current = null; clearInterval(poll); clearInterval(expiry); window.removeEventListener("focus", focus); document.removeEventListener("visibilitychange", focus); };
  }, [refresh]);
  return <Context.Provider value={{ status, refresh }}>{children}</Context.Provider>;
}
const flagText = (value: Flag | undefined, yes: string, no: string) => value === true ? yes : value === false ? no : "Nicht prüfbar";
const names = { inbox: "Eingang", corrections: "Korrekturen", notifications: "Benachrichtigungen", tls: "HTTPS-Zertifikat" };
const opportunities = { inbox: "alle 5 Minuten", corrections: "alle 15 Minuten", notifications: "jede Minute", tls: "stündlich" };
export function OperationsCard() {
  const { status } = useOperations(), overall = status?.state ?? "unknown";
  return <Paper withBorder p="lg" mb="xl" aria-labelledby="operations-heading" data-testid="operations-card">
    <Group justify="space-between" mb="sm"><Title order={2} id="operations-heading">Betriebsstatus</Title><Badge color={stateColor[overall]} variant="light">{stateLabel[overall]}</Badge></Group>
    {!status || status.reason ? <Alert color="gray" mb="md">Kein frischer, zur laufenden Installation passender Betriebsnachweis verfügbar.</Alert> : <Text size="xs" c="dimmed" mb="md">Hoststand {dateTime(status.generated_at!)} · geprüft {dateTime(status.checked_at)} · Europe/Berlin</Text>}
    <Text size="sm">Startdienst: {flagText(status?.startup.configured, "eingerichtet", "nicht eingerichtet")} · {flagText(status?.startup.active, "aktiv", "inaktiv")} · Portal: {flagText(status?.startup.ready, "bereit", "nicht bereit")}</Text>
    <Text size="sm">Importablage: {flagText(status?.mounts.importer, "geprüft", "nicht verfügbar")} · HTTPS-Quelle: {flagText(status?.mounts.tls_source, "geprüft", "nicht verfügbar")}</Text>
    <Text size="sm" mb="md">{flagText(status?.processing_running, "Verarbeitung läuft", "Keine Verarbeitung aktiv")} · Ablaufstopp: {flagText(status?.draining, "gesetzt", "nicht gesetzt")}</Text>
    <Table.ScrollContainer minWidth={760}><Table verticalSpacing="sm"><Table.Thead><Table.Tr><Table.Th>Aufgabe</Table.Th><Table.Th>Zeitplan</Table.Th><Table.Th>Ausführung</Table.Th><Table.Th>Letztes Ergebnis</Table.Th><Table.Th>Nächste Gelegenheit</Table.Th></Table.Tr></Table.Thead><Table.Tbody>
      {jobNames.map(name => { const job = status?.jobs[name], state = job?.state ?? "unknown"; return <Table.Tr key={name}>
        <Table.Td><Text size="sm" fw={600}>{names[name]}</Text><Text size="xs" c="dimmed">{opportunities[name]} · Berlin</Text></Table.Td>
        <Table.Td><Badge color={stateColor[state]} variant="light">{stateLabel[state]}</Badge><Text size="xs" mt={4}>{flagText(job?.configured, "Eingerichtet", "Nicht eingerichtet")}</Text></Table.Td>
        <Table.Td><Text size="sm">{flagText(job?.running, "Läuft", "Kein Lauf aktiv")}</Text>{job?.blocked === true && <Text size="xs" c="orange">Derzeit zurückgestellt</Text>}</Table.Td>
        <Table.Td><Text size="sm">{resultLabel[job?.last_result ?? "unknown"]}</Text><Text size="xs" c="dimmed">{job?.last_run_at == null ? "—" : dateTime(job.last_run_at)}</Text></Table.Td>
        <Table.Td><Text size="sm">{job?.next_run_at == null ? "Nicht belegt" : dateTime(job.next_run_at)}</Text></Table.Td>
      </Table.Tr>; })}
    </Table.Tbody></Table></Table.ScrollContainer>
    <Text size="xs" c="dimmed" mt="md">Zeitpläne bieten Startgelegenheiten. Größere Vorgänge können mehrere Läufe benötigen. Der Eingangsstichtag ist der 23.11.2026, 00:00 Uhr Europe/Berlin.</Text>
    <Text size="xs" c="dimmed" mt={4}>Startdienst zuletzt: {resultLabel[status?.startup.last_result ?? "unknown"]}{status?.startup.last_run_at == null ? "" : " · " + dateTime(status.startup.last_run_at)}</Text>
  </Paper>;
}
