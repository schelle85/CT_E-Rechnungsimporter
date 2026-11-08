import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Group,
  NumberInput,
  Paper,
  PasswordInput,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { api } from "./api";
type Settings = {
  servers: string[];
  port: number;
  search_base: string;
  bind_user: string;
  admin_group: string;
  reader_group: string;
  connect_timeout: number;
  receive_timeout: number;
};
type Config = { version: number; settings: Settings; password_set: boolean; can_edit: boolean };
type Audit = {
  id: number;
  occurred_at: number;
  actor: string;
  action: string;
  result: string;
  changed_fields: string[];
  config_id: number | null;
};
export default function AdminPanel({
  readOnly,
  csrfToken,
  onActivated,
}: {
  readOnly: boolean;
  csrfToken: string;
  onActivated: () => Promise<void>;
}) {
  const [config, setConfig] = useState<Config | null>(null),
    [rows, setRows] = useState<Audit[]>([]),
    [error, setError] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false);
  const canEdit = !readOnly && config?.can_edit === true;
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Config>("/api/admin/config"),
      api<{ items: Audit[] }>("/api/admin/audit"),
    ])
      .then(([c, a]) => {
        if (active) {
          setConfig(c);
          setRows(a.items);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setConfig((c) =>
      c ? { ...c, settings: { ...c.settings, [key]: value } } : c,
    );
  return (
    <Stack>
      {error && <Alert color="red">{error}</Alert>}
      <Alert color="blue" title={readOnly ? "Schreibgeschützte Ansicht" : "Geprüfte Änderungen"}>
        {readOnly ? "Sie können Einstellungen und Protokoll lesen. Änderungen erfordern Verwaltungsrecht." : "Vor der Aktivierung werden alle LDAP-Server und beide Gruppen geprüft. Der letzte aktive Stand bleibt erhalten. Eine Aktivierung beendet bestehende Sitzungen."}
      </Alert>
      {config && (
        <Paper withBorder p="xl">
          {!canEdit ? <>
            <Title order={2} mb="lg">LDAP-Verbindung · Stand {config.version}</Title>
            <dl className="details">{[
              ["LDAPS-Server",config.settings.servers.join(", ")],
              ["LDAPS-Port",String(config.settings.port)],
              ["Suchbasis",config.settings.search_base],
              ["Bindkonto",config.settings.bind_user],
              ["Verwaltungsgruppe",config.settings.admin_group],
              ["Lesegruppe",config.settings.reader_group],
              ["Verbindungs-Timeout",config.settings.connect_timeout+" s"],
              ["Antwort-Timeout",config.settings.receive_timeout+" s"],
            ].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          </> : <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!canEdit) return;
              setBusy(true);
              setError("");
              try {
                await api(
                  "/api/admin/config",
                  {
                    method: "PUT",
                    body: JSON.stringify({
                      expected_version: config.version,
                      settings: config.settings,
                      ...(password ? { bind_password: password } : {}),
                    }),
                  },
                  csrfToken,
                );
                setPassword("");
                await onActivated();
              } catch (e) {
                setError(
                  e instanceof Error
                    ? e.message
                    : "Konfiguration nicht aktiviert.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <Title order={2} mb="lg">
              LDAP-Verbindung · Stand {config.version}
            </Title>
            <fieldset disabled={busy} className="settings-fieldset">
              <div className="settings-grid">
                <Stack>
                  <Textarea
                    label="LDAPS-Server (FQDN, einer je Zeile)"
                    value={config.settings.servers.join("\n")}
                    onChange={(e) =>
                      update("servers", e.currentTarget.value.split("\n"))
                    }
                    required
                    autosize
                    minRows={3}
                  />
                  <NumberInput
                    label="LDAPS-Port"
                    min={1}
                    max={65535}
                    value={config.settings.port}
                    onChange={(v) => update("port", Number(v))}
                  />
                  <TextInput
                    label="Suchbasis (DN)"
                    value={config.settings.search_base}
                    onChange={(e) =>
                      update("search_base", e.currentTarget.value)
                    }
                    required
                  />
                  <TextInput
                    label="Bindkonto (UPN oder DN)"
                    value={config.settings.bind_user}
                    onChange={(e) => update("bind_user", e.currentTarget.value)}
                    required
                  />
                  <PasswordInput
                    label="Bindkennwort ersetzen"
                    description={
                      config.password_set
                        ? "Kennwort hinterlegt. Leer lassen, um es beizubehalten."
                        : "Kennwort durch Betreiber hinterlegen."
                    }
                    value={password}
                    onChange={(e) => setPassword(e.currentTarget.value)}
                    autoComplete="new-password"
                    maxLength={1024}
                  />
                </Stack>
                <Stack>
                  <TextInput
                    label="Verwaltungsgruppe (direkter Gruppen-DN)"
                    value={config.settings.admin_group}
                    onChange={(e) =>
                      update("admin_group", e.currentTarget.value)
                    }
                    required
                  />
                  <TextInput
                    label="Lesegruppe (direkter Gruppen-DN)"
                    value={config.settings.reader_group}
                    onChange={(e) =>
                      update("reader_group", e.currentTarget.value)
                    }
                    required
                  />
                  <NumberInput
                    label="Verbindungs-Timeout (Sekunden)"
                    min={1}
                    max={5}
                    value={config.settings.connect_timeout}
                    onChange={(v) => update("connect_timeout", Number(v))}
                  />
                  <NumberInput
                    label="Antwort-Timeout (Sekunden)"
                    min={1}
                    max={5}
                    value={config.settings.receive_timeout}
                    onChange={(v) => update("receive_timeout", Number(v))}
                  />
                  <Text c="dimmed" size="sm">
                    LDAPS mit geprüfter CA und Serveridentität ist
                    verpflichtend. LDAP-Referrals werden nicht verfolgt. CA und
                    Schlüssel verwaltet der Betreiber.
                  </Text>
                </Stack>
              </div>
              <Group justify="flex-end" mt="xl">
                <Button type="submit" loading={busy}>
                  Prüfen und aktivieren
                </Button>
              </Group>
            </fieldset>
          </form>}
        </Paper>
      )}
      <Paper withBorder className="panel">
        <div className="panel-heading">
          <Title order={2}>Änderungs- und Zugriffsprotokoll</Title>
          <Text c="dimmed" size="sm">
            Letzte 100 Einträge · keine Kennwortinhalte
          </Text>
        </div>
        <Table.ScrollContainer minWidth={650}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Zeitpunkt</Table.Th>
                <Table.Th>Konto</Table.Th>
                <Table.Th>Aktion</Table.Th>
                <Table.Th>Ergebnis</Table.Th>
                <Table.Th>Stand</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td>
                    {new Date(r.occurred_at * 1000).toLocaleString("de-DE")}
                  </Table.Td>
                  <Table.Td>{r.actor}</Table.Td>
                  <Table.Td>{r.action}</Table.Td>
                  <Table.Td>{r.result}</Table.Td>
                  <Table.Td>{r.config_id ?? "–"}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Paper>
    </Stack>
  );
}
