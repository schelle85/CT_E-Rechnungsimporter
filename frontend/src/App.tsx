import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Card, Drawer, Group, Pagination, Paper, Select, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { api, type User } from "./api";
import AdminPanel from "./AdminPanel";
import ProcessingControls from "./ProcessingControls";
import ProcessDialog from "./ProcessDialog";
import { type Attachment, type PageResult, type Process, type ProcessDetail, type ProcessingSettings, type Stats, StatusBadge, dateTime, reasonText } from "./processTypes";

type Page = "overview" | "processes" | "unknown" | "archive" | "admin";
const pages: { id: Page; label: string; icon: string }[] = [
  { id: "overview", label: "Übersicht", icon: "◫" }, { id: "processes", label: "Vorgänge", icon: "☷" },
  { id: "unknown", label: "Unbekannt", icon: "?" }, { id: "archive", label: "Archiv", icon: "▤" },
  { id: "admin", label: "Administration", icon: "⚙" },
];
const stateOptions = [
  { value: "registered", label: "Wartet" }, { value: "processing", label: "In Bearbeitung" },
  { value: "closing", label: "Abschluss läuft" }, { value: "unknown", label: "Offene unbekannte Anhänge" },
  { value: "done", label: "Abgeschlossen" }, { value: "errors", label: "Fehler / Klärung erforderlich" }, { value: "failed", label: "Fehler" }, { value: "operator_required", label: "Klärung erforderlich" },
];
export default function App({ user, csrfToken, onLogout, onReauthenticate }: {
  user: User; csrfToken: string; onLogout: () => Promise<void>; onReauthenticate: () => Promise<void>;
}) {
  const [page, setPage] = useState<Page>("overview"), [mobile, setMobile] = useState(false);
  const [items, setItems] = useState<Process[]>([]), [unknown, setUnknown] = useState<Attachment[]>([]);
  const [stats, setStats] = useState<Stats | null>(null), [settings, setSettings] = useState<ProcessingSettings | null>(null);
  const [total, setTotal] = useState(0), [pageNo, setPageNo] = useState(1), [version, setVersion] = useState(0);
  const [query, setQuery] = useState(""), [state, setState] = useState<string | null>(null), [category, setCategory] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<string | null>(null), [from, setFrom] = useState(""), [to, setTo] = useState("");
  const [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [detail, setDetail] = useState<ProcessDetail | null>(null), [initialAttachment, setInitialAttachment] = useState<string | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const detailSequence = useRef(0);
  const role = user.role === "admin" ? "Verwaltung" : "Lesen";
  function nav(next: Page) { setPage(next); setMobile(false); setPageNo(1); setQuery(""); setState(null); setCategory(null); setDuplicate(null); setFrom(""); setTo(""); }
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(""); setItems([]); setUnknown([]); setStats(null); setTotal(0);
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ view: page === "archive" ? "archive" : "active" });
      if (page !== "overview" && query.trim()) params.set("search", query.trim());
      if (page === "processes" || page === "archive") {
        if (state) params.set("state", state); if (category) params.set("category", category);
        if (duplicate) params.set("duplicate", duplicate); if (from) params.set("received_from", from); if (to) params.set("received_to", to);
      }
      const filters = params.toString();
      params.set("page", String(pageNo)); params.set("page_size", page === "overview" ? "5" : "25");
      const list = page === "unknown" ? api<PageResult<Attachment>>("/api/unknown?" + params, { signal: controller.signal }) : api<PageResult<Process>>("/api/processes?" + params, { signal: controller.signal });
      Promise.all([list, api<Stats>("/api/processes/stats?" + filters, { signal: controller.signal }), api<ProcessingSettings>("/api/admin/processing", { signal: controller.signal })])
        .then(([result, counts, controls]) => {
          if (controller.signal.aborted) return;
          if (page === "unknown") setUnknown((result as PageResult<Attachment>).items); else setItems((result as PageResult<Process>).items);
          setTotal(result.total); setStats(counts); setSettings(controls);
        }).catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Vorgänge konnten nicht geladen werden."); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, query ? 250 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [page, query, state, category, duplicate, from, to, pageNo, version]);
  async function openDetail(key: string, attachment: string | null = null) {
    const sequence = ++detailSequence.current;
    setDetailBusy(true); setError("");
    try { const value = await api<ProcessDetail>("/api/processes/" + key);
      if (sequence === detailSequence.current) { setDetail(value); setInitialAttachment(attachment); }
    } catch (e) { if (sequence === detailSequence.current) setError(e instanceof Error ? e.message : "Details sind nicht verfügbar."); }
    finally { if (sequence === detailSequence.current) setDetailBusy(false); }
  }
  async function changed() {
    if (detail) {
      const key = detail.id, value = await api<ProcessDetail>("/api/processes/" + key);
      setDetail(current => current?.id === key ? value : current);
    }
    setVersion(value => value + 1);
  }
  const navigation = <>
    <div className="brand"><span className="brand-mark">E</span><div>E-Rechnungen<small>IMPORTER</small></div></div>
    <Text className="nav-section">ARBEITSPLATZ</Text><nav aria-label="Hauptnavigation">{pages.map(p =>
      <button key={p.id} className={page === p.id ? "nav-item active" : "nav-item"} onClick={() => nav(p.id)} aria-current={page === p.id ? "page" : undefined}>
        <span aria-hidden="true">{p.icon}</span>{p.label}
      </button>)}</nav>
    <div className="sidebar-bottom"><span className="status-dot" /><div>Manueller Betrieb<small>Automatischer Import inaktiv</small></div></div>
  </>;
  const processRows = <Table.ScrollContainer minWidth={760}><Table verticalSpacing="md" highlightOnHover>
    <Table.Thead><Table.Tr><Table.Th>Eingang / Vorgang</Table.Th><Table.Th>Anhänge</Table.Th><Table.Th>Kategorien</Table.Th><Table.Th>Status</Table.Th><Table.Th><span className="sr-only">Details</span></Table.Th></Table.Tr></Table.Thead>
    <Table.Tbody>{items.map(item => <Table.Tr key={item.id}>
      <Table.Td><Text size="sm" fw={600}>{dateTime(item.received_at)}</Text><Text size="xs" c="dimmed">{item.id.slice(0, 12)}</Text></Table.Td>
      <Table.Td><Text size="sm" fw={600}>{item.names.join(", ") || "Keine Anhänge"}</Text><Text size="xs" c="dimmed">{item.attachment_count} Anhänge · {item.unknown_open} unbekannt{item.duplicate_count ? " · " + item.duplicate_count + " Dublette(n)" : ""}</Text></Table.Td>
      <Table.Td><Text size="sm">{item.categories.join(", ") || "Offen"}</Text></Table.Td>
      <Table.Td><StatusBadge value={item.state} /></Table.Td>
      <Table.Td><Button variant="subtle" size="xs" onClick={() => openDetail(item.id)} disabled={detailBusy} aria-label={"Details zu " + item.id}>Ansehen →</Button></Table.Td>
    </Table.Tr>)}</Table.Tbody></Table>
    {!items.length && <Text ta="center" c="dimmed" py="xl">{loading ? "Vorgänge werden geladen …" : error ? "Daten konnten nicht geladen werden." : page === "archive" ? "Keine archivierten Vorgänge für diese Auswahl." : "Keine Vorgänge für diese Auswahl."}</Text>}
  </Table.ScrollContainer>;
  return <div className="app"><aside className="sidebar">{navigation}</aside>
    <Drawer opened={mobile} onClose={() => setMobile(false)} title="Navigation" size="xs">{navigation}</Drawer>
    <div className="workspace"><header className="topbar"><Group gap="sm"><Button className="mobile-toggle" variant="subtle" onClick={() => setMobile(true)} aria-label="Navigation öffnen">☰</Button>
      <Text size="sm" c="dimmed">Arbeitsplatz <span className="breadcrumb">/ {pages.find(p => p.id === page)?.label}</span></Text></Group>
      <Group gap="sm"><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><div><Text size="sm" fw={600}>{user.username}</Text><Text size="xs" c="dimmed">{role} · AD</Text></div><Button size="xs" variant="subtle" onClick={onLogout}>Abmelden</Button></Group>
    </header><main id="main-content">
      <Group justify="space-between" align="flex-end" mb="xl" gap="md"><div><Text className="eyebrow">E-RECHNUNGSIMPORTER</Text><Title order={1}>{pages.find(p => p.id === page)?.label}</Title>
        <Text c="dimmed" mt={6}>{page === "unknown" ? "Unbekannte Anhänge einzeln prüfen und ausdrücklich zuordnen." : page === "archive" ? "Ältere Protokolle bleiben erhalten und können gelesen werden." : page === "admin" ? "Verbindungen, Zugriffsrechte und Verarbeitungseinstellungen verwalten." : "Eingänge, Entscheidungen und tatsächliche Ergebnisse nachvollziehen."}</Text></div>
        <Group><Badge variant="light">{role} · AD geprüft</Badge><Button variant="light" onClick={() => setVersion(v => v + 1)} loading={loading}>Aktualisieren</Button></Group>
      </Group>
      {error && <Alert role="alert" color="red" mb="lg">{error}</Alert>}
      {page === "overview" && <>
        <div className="metric-grid">{[
          { label: "Vorgänge", value: stats?.messages, note: "Aktive Verarbeitungsprotokolle", color: "blue", target: "processes" as Page },
          { label: "Unbekannt", value: stats?.unknown_open, note: "Offene Anhänge · einzeln zuordnen", color: "yellow", target: "unknown" as Page },
          { label: "Dubletten", value: stats?.duplicates, note: "Bestätigte Dublettenbelege", color: "blue", target: "processes" as Page },
          { label: "Fehler", value: stats?.errors, note: "Fehlgeschlagen oder Klärung erforderlich", color: "red", target: "processes" as Page },
        ].map(metric => <Card key={metric.label} withBorder className={"metric metric-" + metric.color}>
          <Text size="sm" c="dimmed">{metric.label}</Text><Text className="metric-value">{metric.value ?? "—"}</Text><Text size="xs" c="dimmed">{metric.note}</Text>
          <Button variant="subtle" size="xs" mt="xs" onClick={() => { nav(metric.target); if (metric.label === "Dubletten") setDuplicate("true"); if (metric.label === "Fehler") setState("errors"); }}>Ansehen →</Button>
        </Card>)}</div>
        <Paper withBorder className="panel"><Group justify="space-between" className="panel-heading"><div><Title order={2}>Letzte Vorgänge</Title><Text size="sm" c="dimmed">Aus dem dauerhaften Verarbeitungsprotokoll</Text></div><Button variant="subtle" onClick={() => nav("processes")}>Alle ansehen →</Button></Group>{processRows}</Paper>
      </>}
      {(page === "processes" || page === "archive") && <Paper withBorder className="panel">
        <Group justify="space-between" className="panel-heading"><Title order={2}>{page === "archive" ? "Archivierte Vorgänge" : "Vorgänge"}</Title><Badge variant="light">{loading ? "Wird geladen" : total + " Vorgänge"}</Badge></Group>
        {page === "archive" && <Text size="sm" c="dimmed" px="lg" pb="lg">Zwei Kalenderjahre ab erster Protokollanlage in der aktiven Ansicht, danach hier schreibgeschützt. Es werden keine Protokolle gelöscht.</Text>}
        <div className="process-filters">
          <TextInput label="Suche" placeholder="Datei, Vorgang, Kategorie oder Ablageziel" value={query} maxLength={200} onChange={e => { setQuery(e.currentTarget.value); setPageNo(1); }} />
          <Select label="Status" placeholder="Alle Status" clearable data={stateOptions} value={state} onChange={value => { setState(value); setPageNo(1); }} />
          <Select label="Kategorie" placeholder="Alle Kategorien" clearable data={["E-Rechnung", "PDF", "Zahlungsavis", "Mahnung"]} value={category} onChange={value => { setCategory(value); setPageNo(1); }} />
          <Select label="Dubletten" placeholder="Alle" clearable data={[{ value: "true", label: "Mit Dubletten" }, { value: "false", label: "Ohne Dubletten" }]} value={duplicate} onChange={value => { setDuplicate(value); setPageNo(1); }} />
          <TextInput type="date" label="Eingang von" value={from} onChange={e => { setFrom(e.currentTarget.value); setPageNo(1); }} />
          <TextInput type="date" label="Eingang bis" value={to} onChange={e => { setTo(e.currentTarget.value); setPageNo(1); }} />
        </div>{processRows}
        {total > 25 && <Pagination total={Math.ceil(total / 25)} value={pageNo} onChange={setPageNo} p="lg" />}
      </Paper>}
      {page === "unknown" && <Paper withBorder className="panel"><Group justify="space-between" className="panel-heading"><Title order={2}>Offene unbekannte Anhänge</Title><Badge color="yellow">{loading ? "Wird geladen" : total + " Anhänge"}</Badge></Group>
        <TextInput mx="lg" mb="lg" label="Suche" placeholder="Datei oder Vorgang" value={query} maxLength={200} onChange={e => { setQuery(e.currentTarget.value); setPageNo(1); }} />
        <Table.ScrollContainer minWidth={650}><Table verticalSpacing="md"><Table.Thead><Table.Tr><Table.Th>Anhang</Table.Th><Table.Th>Befund</Table.Th><Table.Th>Status</Table.Th><Table.Th>Prüfung</Table.Th></Table.Tr></Table.Thead><Table.Tbody>
          {unknown.map(row => <Table.Tr key={row.id}><Table.Td><Text fw={600} size="sm">{row.name}</Text><Text size="xs" c="dimmed">Vorgang {row.message_id.slice(0, 12)}</Text></Table.Td><Table.Td><Text size="sm">{reasonText(row.current_finding)}</Text></Table.Td><Table.Td><StatusBadge value={row.status} /></Table.Td><Table.Td><Button size="xs" variant="light" disabled={detailBusy} onClick={() => openDetail(row.message_id, row.id)}>Original und Zuordnung</Button></Table.Td></Table.Tr>)}
        </Table.Tbody></Table>{!unknown.length && <Text ta="center" c="dimmed" py="xl">{loading ? "Anhänge werden geladen …" : error ? "Daten konnten nicht geladen werden." : "Keine offenen unbekannten Anhänge für diese Auswahl."}</Text>}</Table.ScrollContainer>
        {total > 25 && <Pagination total={Math.ceil(total / 25)} value={pageNo} onChange={setPageNo} p="lg" />}
      </Paper>}
      {page === "admin" && <Stack><ProcessingControls csrfToken={csrfToken} onSaved={() => setVersion(v => v + 1)} /><AdminPanel readOnly={user.role !== "admin"} csrfToken={csrfToken} onActivated={onReauthenticate} /></Stack>}
      <footer><span>E-Rechnungsimporter · Verarbeitungsprotokolle</span><span>Automatischer Import inaktiv</span></footer>
    </main></div>
    <ProcessDialog detail={detail} initialAttachment={initialAttachment} settings={settings} canEdit={user.role === "admin"} csrfToken={csrfToken}
      onClose={() => { detailSequence.current++; setDetail(null); setInitialAttachment(null); }} onChanged={changed} />
  </div>;
}