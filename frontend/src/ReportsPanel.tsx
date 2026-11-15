import { useEffect, useState } from "react";
import { Alert, Button, Card, Group, Paper, Select, Text, TextInput, Title } from "@mantine/core";
import { api } from "./api";
import { dateTime } from "./processTypes";

export type Report = { period: string; start: number; end: number; as_of: number; timezone: string; synthetic: false; counts: Record<string, number> };
const labels: Record<string, string> = { messages: "Vorgänge", attachments: "Anhänge", unknown_open: "Offene unbekannte Anhänge", stored_receipts: "Bestätigte Ablage / Dubletten", duplicates: "Dubletten", attachment_errors: "Technische Anhangsfehler", blocked_messages: "Vorgänge mit Klärungsbedarf", "E-Rechnung": "E-Rechnungen", PDF: "PDF-Rechnungen", Zahlungsavis: "Zahlungsavise", Mahnung: "Mahnungen" };
export default function ReportsPanel() {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Berlin" });
  const [period, setPeriod] = useState("daily"), [anchor, setAnchor] = useState(today);
  const [from, setFrom] = useState(today), [to, setTo] = useState(today);
  const [report, setReport] = useState<Report | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); setError(""); setReport(null);
    try {
      const query = new URLSearchParams({ period });
      if (period === "range") { query.set("from_date", from); query.set("to_date", to); } else query.set("anchor", anchor);
      setReport(await api<Report>("/api/admin/reports?" + query));
    } catch (e) { setError(e instanceof Error ? e.message : "Bericht nicht verfügbar."); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);
  return <Paper withBorder p="xl"><Title order={2}>Berichte</Title>
    <Text c="dimmed" size="sm" mt="xs" mb="lg">Echte Werte aus dem Verarbeitungsjournal. Die Auswahl richtet sich nach der ersten Protokollanlage in Europe/Berlin. Das Ansehen versendet keine Mail.</Text>
    <form onSubmit={e => { e.preventDefault(); void load(); }}><Group align="flex-end" mb="lg">
      <Select label="Berichtszeitraum" value={period} onChange={v => setPeriod(v || "daily")} allowDeselect={false} data={[{ value: "daily", label: "Tagesübersicht" }, { value: "weekly", label: "Wochenübersicht (Mo–So)" }, { value: "range", label: "Zeitraum wählen" }]} />
      {period === "range" ? <><TextInput type="date" label="Protokollanlage von" value={from} onChange={e => setFrom(e.currentTarget.value)} required /><TextInput type="date" label="Protokollanlage bis einschließlich" value={to} min={from} onChange={e => setTo(e.currentTarget.value)} required /></> : <TextInput type="date" label={period === "weekly" ? "Tag in der gewünschten Woche" : "Tag"} value={anchor} onChange={e => setAnchor(e.currentTarget.value)} required />}
      <Button type="submit" loading={busy}>Bericht anzeigen</Button>
    </Group></form>
    {period === "range" && <Text size="xs" c="dimmed" mb="md">Bis zu 366 Tage je Abfrage. Ältere Protokolle bleiben über die Zeitraumwahl erreichbar.</Text>}
    {error && <Alert color="red" role="alert">{error}</Alert>}
    {busy && <Text role="status">Bericht wird geladen …</Text>}
    {report && <><Text size="sm" mb="xs">Zeitraum: {dateTime(report.start)} bis {dateTime(report.end - 1)}</Text>
      <Text size="sm" c="dimmed" mb="lg">Erstellstand: {dateTime(report.as_of)} · {report.timezone}. Aktuelle Zustände der im Zeitraum erstmals protokollierten Vorgänge.</Text>
      {report.counts.messages === 0 && <Alert color="blue" mb="lg">Keine Vorgänge in diesem Zeitraum. Das Journal enthält für diese Auswahl keine Einträge.</Alert>}
      <div className="metric-grid">{Object.entries(labels).map(([key, label]) => <Card withBorder key={key}><Text size="sm" c="dimmed">{label}</Text><Text size="xl" fw={700}>{report.counts[key]}</Text></Card>)}</div>
    </>}
  </Paper>;
}
