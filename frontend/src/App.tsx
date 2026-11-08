import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Drawer,
  Group,
  Modal,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
type Page =
  "overview" | "processes" | "admin" | "notifications" | "archive" | "login";
type Item = {
  id: string;
  received: string;
  sender: string;
  subject: string;
  category: string;
  status: string;
  filename: string;
  reason: string;
  size: string;
};
const pages: { id: Page; label: string; icon: string }[] = [
  { id: "overview", label: "Übersicht", icon: "◫" },
  { id: "processes", label: "Verarbeitung", icon: "☷" },
  { id: "archive", label: "Archiv", icon: "▤" },
  { id: "notifications", label: "Meldungen", icon: "◇" },
  { id: "admin", label: "Administration", icon: "⚙" },
  { id: "login", label: "Anmeldung", icon: "↪" },
];
const colors: Record<string, string> = {
  Erfolgreich: "teal",
  Prüfen: "yellow",
  Fehler: "red",
  Dublette: "gray",
};
export default function App() {
  const [page, setPage] = useState<Page>("overview"),
    [mobile, setMobile] = useState(false),
    [role, setRole] = useState("Verwaltung");
  const [items, setItems] = useState<Item[]>([]),
    [detail, setDetail] = useState<Item | null>(null);
  const [query, setQuery] = useState(""),
    [status, setStatus] = useState<string | null>(null),
    [apiState, setApiState] = useState("Wird geprüft");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/demo/processes", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((d) => setItems(d.items))
      .catch((e) => {
        if (e.name !== "AbortError")
          setApiState("Vorschau-API nicht erreichbar");
      });
    fetch("/api/health/ready", { signal: controller.signal })
      .then((r) =>
        setApiState(
          r.ok ? "Grundgerüst bereit" : "Datenbank noch nicht bereit",
        ),
      )
      .catch(() => {
        if (!controller.signal.aborted) setApiState("API noch nicht bereit");
      });
    return () => controller.abort();
  }, []);
  const nav = (p: Page) => {
    setPage(p);
    setMobile(false);
  };
  const filtered = items.filter(
    (i) =>
      (!status || i.status === status) &&
      [i.id, i.sender, i.subject, i.filename]
        .join(" ")
        .toLocaleLowerCase("de")
        .includes(query.toLocaleLowerCase("de")),
  );
  const navigation = (
    <>
      <div className="brand">
        <span className="brand-mark">E</span>
        <div>
          E-Rechnungen<small>IMPORTER</small>
        </div>
      </div>
      <Text className="nav-section">ARBEITSPLATZ</Text>
      <nav aria-label="Hauptnavigation">
        {pages.map((p) => (
          <button
            key={p.id}
            className={page === p.id ? "nav-item active" : "nav-item"}
            onClick={() => nav(p.id)}
            aria-current={page === p.id ? "page" : undefined}
          >
            <span aria-hidden="true">{p.icon}</span>
            {p.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <span className="status-dot" />
        <div>
          Entwurfsumgebung<small>Keine Verarbeitung aktiv</small>
        </div>
      </div>
    </>
  );
  const rows = (list: Item[]) => (
    <Table.ScrollContainer minWidth={750}>
      <Table verticalSpacing="md" highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Eingang / Vorgang</Table.Th>
            <Table.Th>Absender und Betreff</Table.Th>
            <Table.Th>Kategorie</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>
              <span className="sr-only">Details</span>
            </Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {list.map((i) => (
            <Table.Tr key={i.id}>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {i.received}
                </Text>
                <Text size="xs" c="dimmed">
                  {i.id}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {i.sender}
                </Text>
                <Text size="xs" c="dimmed">
                  {i.subject}
                </Text>
              </Table.Td>
              <Table.Td>
                <Badge color="blue" variant="light" radius="sm">
                  {i.category}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Badge color={colors[i.status]} variant="light" radius="sm">
                  {i.status}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Button
                  variant="subtle"
                  size="xs"
                  onClick={() => setDetail(i)}
                  aria-label={"Details zu " + i.id}
                >
                  Ansehen →
                </Button>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {list.length === 0 && (
        <Text ta="center" c="dimmed" py="xl">
          {items.length
            ? "Keine passenden Beispielvorgänge."
            : "Noch keine Vorschau geladen."}
        </Text>
      )}
    </Table.ScrollContainer>
  );
  return (
    <div className="app">
      <aside className="sidebar">{navigation}</aside>
      <Drawer
        opened={mobile}
        onClose={() => setMobile(false)}
        title="Navigation"
        size="xs"
      >
        {navigation}
      </Drawer>
      <div className="workspace">
        <header className="topbar">
          <Group gap="sm">
            <Button
              className="mobile-toggle"
              variant="subtle"
              onClick={() => setMobile(true)}
              aria-label="Navigation öffnen"
            >
              ☰
            </Button>
            <Text size="sm" c="dimmed">
              Arbeitsplatz{" "}
              <span className="breadcrumb">
                / {pages.find((p) => p.id === page)?.label}
              </span>
            </Text>
          </Group>
          <Group gap="sm">
            <span className="avatar">DV</span>
            <div>
              <Text size="sm" fw={600}>
                Designvorschau
              </Text>
              <Text size="xs" c="dimmed">
                {role} · simuliert
              </Text>
            </div>
          </Group>
        </header>
        <main id="main-content">
          <Alert
            color="blue"
            variant="light"
            className="preview-banner"
            title="Synthetische Vorschau – keine produktive Verarbeitung"
          >
            Alle Vorgänge sind erfunden. Es werden keine E-Mails gelesen,
            Dateien abgelegt oder Meldungen versendet.
          </Alert>
          <Group justify="space-between" align="flex-end" mb="xl" gap="md">
            <div>
              <Text className="eyebrow">E-RECHNUNGSIMPORTER</Text>
              <Title order={1}>{pages.find((p) => p.id === page)?.label}</Title>
              <Text c="dimmed" mt={6}>
                {page === "overview"
                  ? "Alles Wichtige zum Rechnungseingang auf einen Blick."
                  : page === "processes"
                    ? "Eingänge und Entscheidungen nachvollziehbar prüfen."
                    : page === "archive"
                      ? "Vorgesehener Zugang zu älteren Verarbeitungsprotokollen."
                      : page === "admin"
                        ? "Verbindungen und Zugriffsrechte zentral verwalten."
                        : page === "notifications"
                          ? "Geplante automatische Meldungen im Überblick."
                          : "Zugang mit Ihrem bestehenden Windows-Konto."}
              </Text>
            </div>
            <div>
              <Text size="xs" c="dimmed" mb={5}>
                Rollenansicht · keine Anmeldung
              </Text>
              <SegmentedControl
                size="xs"
                value={role}
                onChange={setRole}
                data={["Verwaltung", "Lesen"]}
              />
            </div>
          </Group>
          {page === "overview" && (
            <>
              <div className="metric-grid">
                {[
                  {
                    label: "Beispiele insgesamt",
                    value: items.length,
                    note: "Synthetischer Datensatz",
                    color: "blue",
                  },
                  {
                    label: "Erfolgreich",
                    value: items.filter((i) => i.status === "Erfolgreich")
                      .length,
                    note: "Beispiel: Ablage abgeschlossen",
                    color: "teal",
                  },
                  {
                    label: "Zu prüfen",
                    value: items.filter((i) => i.status === "Prüfen").length,
                    note: "Beispiel: fachliche Rückfrage",
                    color: "yellow",
                  },
                  {
                    label: "Fehler",
                    value: items.filter((i) => i.status === "Fehler").length,
                    note: "Beispiel: Erkennung fehlgeschlagen",
                    color: "red",
                  },
                ].map((m) => (
                  <Card
                    key={m.label}
                    withBorder
                    className={"metric metric-" + m.color}
                  >
                    <Text size="sm" c="dimmed">
                      {m.label}
                    </Text>
                    <Text className="metric-value">{m.value}</Text>
                    <Text size="xs" c="dimmed">
                      {m.note}
                    </Text>
                  </Card>
                ))}
              </div>
              <div className="overview-grid">
                <Paper withBorder className="panel">
                  <Group justify="space-between" className="panel-heading">
                    <div>
                      <Title order={2}>Letzte Vorgänge</Title>
                      <Text size="sm" c="dimmed">
                        Beispielhafte Verarbeitungsergebnisse
                      </Text>
                    </div>
                    <Button
                      variant="subtle"
                      onClick={() => setPage("processes")}
                    >
                      Alle ansehen →
                    </Button>
                  </Group>
                  {rows(items.slice(0, 4))}
                </Paper>
                <Paper withBorder className="panel system-panel">
                  <Title order={2}>Betriebsübersicht</Title>
                  <Text c="dimmed" size="sm" mt={4}>
                    Technik und geplanter Ablauf
                  </Text>
                  <div className="system-row">
                    <span>API / Datenbank</span>
                    <Badge
                      variant="light"
                      color={
                        apiState === "Grundgerüst bereit" ? "teal" : "gray"
                      }
                    >
                      {apiState}
                    </Badge>
                  </div>
                  <div className="system-row">
                    <span>AD-Anmeldung</span>
                    <Badge color="gray">Geplant</Badge>
                  </div>
                  <div className="system-row">
                    <span>Automatischer Import</span>
                    <Badge color="gray">Inaktiv</Badge>
                  </div>
                  <div className="system-row">
                    <span>Benachrichtigungen</span>
                    <Badge color="gray">Inaktiv</Badge>
                  </div>
                  <div className="next-step">
                    <Text size="sm" fw={600}>
                      Nächster Schritt
                    </Text>
                    <Text size="sm" c="dimmed" mt={5}>
                      Oberfläche und Grundgerüst prüfen. Anschließend die
                      AD-Anmeldung und wirksame Berechtigungen anbinden.
                    </Text>
                  </div>
                </Paper>
              </div>
            </>
          )}
          {page === "processes" && (
            <Paper withBorder className="panel">
              <Group className="panel-heading" justify="space-between">
                <Title order={2}>Vorgänge</Title>
                <Badge variant="light">{filtered.length} Beispiele</Badge>
              </Group>
              <Group px="lg" pb="lg" grow>
                <TextInput
                  label="Suche"
                  placeholder="Vorgang, Absender oder Datei"
                  value={query}
                  onChange={(e) => setQuery(e.currentTarget.value)}
                />
                <Select
                  label="Status"
                  placeholder="Alle Status"
                  clearable
                  data={Object.keys(colors)}
                  value={status}
                  onChange={setStatus}
                />
              </Group>
              {rows(filtered)}
            </Paper>
          )}
          {page === "archive" && (
            <Paper withBorder className="empty-state">
              <div className="empty-icon" aria-hidden="true">
                ▤
              </div>
              <Title order={2}>Ein klarer Blick zurück</Title>
              <Text c="dimmed" maw={520} mx="auto" mt="sm">
                Protokolle bleiben zwei Jahre aktiv. Ältere Einträge werden
                später hier zugänglich sein; eine automatische Löschung ist
                nicht vorgesehen.
              </Text>
              <Badge mt="lg" color="gray">
                Archivfunktion geplant · keine echten Daten
              </Badge>
            </Paper>
          )}
          {page === "admin" && (
            <>
              <Alert color={role === "Lesen" ? "yellow" : "blue"} mb="lg">
                {role === "Lesen"
                  ? "Ansicht für Leseberechtigte: Einstellungen können später nur mit Verwaltungsrecht geändert werden."
                  : "Verwaltungsansicht als Entwurf. Speichern ist bis zur geschützten Backendanbindung gesperrt."}
              </Alert>
              <div className="settings-grid">
                <Paper withBorder p="xl">
                  <Title order={2} mb="lg">
                    AD-Verbindung
                  </Title>
                  <Stack>
                    <TextInput
                      label="LDAP-Server"
                      placeholder="ldaps://dc.example.invalid"
                      disabled
                    />
                    <TextInput
                      label="Suchbasis"
                      placeholder="DC=example,DC=invalid"
                      disabled
                    />
                    <TextInput
                      label="Bindkonto"
                      placeholder="Dienstkonto"
                      disabled
                    />
                    <Text size="sm" c="dimmed">
                      Kennwort und CA-Vertrauen werden geschützt auf dem Server
                      hinterlegt. Die Vorschau nimmt keine Zugangsdaten an.
                    </Text>
                    <Button disabled>Verbindung prüfen · geplant</Button>
                  </Stack>
                </Paper>
                <Paper withBorder p="xl">
                  <Title order={2} mb="lg">
                    Zugriff und Rollen
                  </Title>
                  <Stack>
                    <TextInput
                      label="Gruppe für Verwaltung"
                      placeholder="AD-Gruppe konfigurieren"
                      disabled
                    />
                    <TextInput
                      label="Gruppe für Lesen"
                      placeholder="AD-Gruppe konfigurieren"
                      disabled
                    />
                    <Text size="sm" c="dimmed">
                      Vorgesehen sind direkte Gruppenmitgliedschaften. Die
                      spätere API prüft Rechte bei jedem geschützten Zugriff.
                    </Text>
                    <Button disabled>Einstellungen speichern · geplant</Button>
                  </Stack>
                </Paper>
              </div>
            </>
          )}
          {page === "notifications" && (
            <Paper withBorder className="panel">
              <div className="panel-heading">
                <Title order={2}>Automatische Meldungen</Title>
                <Text c="dimmed" size="sm">
                  Geplante Konfiguration; kein Versand aktiv.
                </Text>
              </div>
              <Table.ScrollContainer minWidth={550}>
                <Table verticalSpacing="lg">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Meldung</Table.Th>
                      <Table.Th>Vorgesehener Anlass</Table.Th>
                      <Table.Th>Status</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {[
                      [
                        "Fehler und Ausfälle",
                        "Erforderliche Verarbeitung fehlgeschlagen",
                      ],
                      ["Tagesübersicht", "Zusammenfassung des Tages"],
                      ["Wochenübersicht", "Zusammenfassung der Woche"],
                      [
                        "Zertifikatswarnung",
                        "Graph-Zertifikat ab 10 Tagen vor Ablauf",
                      ],
                    ].map(([name, reason]) => (
                      <Table.Tr key={name}>
                        <Table.Td fw={600}>{name}</Table.Td>
                        <Table.Td>{reason}</Table.Td>
                        <Table.Td>
                          <Badge color="gray">Geplant</Badge>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
              <Text size="sm" c="dimmed" p="lg">
                Empfänger und Zeitpläne werden später geschützt verwaltet. Es
                gibt keinen manuellen Mail-Editor.
              </Text>
            </Paper>
          )}
          {page === "login" && (
            <Paper withBorder className="login-card">
              <div className="login-symbol" aria-hidden="true">
                ↪
              </div>
              <Title order={2}>Mit Windows-Konto anmelden</Title>
              <Text c="dimmed" mt="sm" mb="xl">
                Die AD-Anmeldung wird im nächsten Schritt angebunden. Bitte hier
                keine echten Zugangsdaten eingeben.
              </Text>
              <Stack>
                <TextInput
                  label="Benutzername"
                  placeholder="In der Vorschau gesperrt"
                  disabled
                />
                <TextInput
                  label="Kennwort"
                  type="password"
                  placeholder="In der Vorschau gesperrt"
                  disabled
                />
                <Button disabled>Anmelden · geplant</Button>
                <Text size="xs" c="dimmed">
                  Keine lokale Benutzer- oder Passwortverwaltung.
                </Text>
              </Stack>
            </Paper>
          )}
          <footer>
            <span>E-Rechnungsimporter · AP01 Designvorschau</span>
            <span>Keine Verarbeitung aktiv</span>
          </footer>
        </main>
      </div>
      <Modal
        opened={!!detail}
        onClose={() => setDetail(null)}
        title="Vorgangsdetails · synthetisches Beispiel"
        size="lg"
      >
        {detail && (
          <Stack>
            <Group justify="space-between">
              <Title order={2}>{detail.id}</Title>
              <Badge color={colors[detail.status]}>{detail.status}</Badge>
            </Group>
            <Text c="dimmed">{detail.subject}</Text>
            <dl className="details">
              {[
                ["Eingang", detail.received],
                ["Absender", detail.sender],
                ["Datei", detail.filename],
                ["Größe", detail.size],
                ["Kategorie", detail.category],
                ["Begründung", detail.reason],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <Alert color="blue">
              Dieser Verlauf ist erfunden. Es wurde keine Datei verarbeitet oder
              abgelegt.
            </Alert>
            <Button disabled>Erneut verarbeiten · später verfügbar</Button>
          </Stack>
        )}
      </Modal>
    </div>
  );
}
