import { useEffect, useState } from "react";
import { Alert, Button, Checkbox, Paper, Stack, Text, Title } from "@mantine/core";
import { api } from "./api";
import { type ProcessingSettings } from "./processTypes";
export default function ProcessingControls({ csrfToken, onSaved }: { csrfToken: string; onSaved: () => void }) {
  const [value, setValue] = useState<ProcessingSettings | null>(null);
  const [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => { api<ProcessingSettings>("/api/admin/processing").then(setValue).catch(e => setNotice(e.message)); }, []);
  async function save() {
    if (!value || !value.can_edit || busy) return;
    setBusy(true); setNotice("");
    try { const saved = await api<ProcessingSettings>("/api/admin/processing", { method: "PUT", body: JSON.stringify({ expected_version: value.version, preview_enabled: value.preview_enabled, retry_enabled: value.retry_enabled }) }, csrfToken);
      setValue(saved); setNotice("Einstellungen gespeichert."); onSaved();
    } catch (e) { setNotice(e instanceof Error ? e.message : "Einstellungen konnten nicht gespeichert werden."); }
    finally { setBusy(false); }
  }
  return <Paper withBorder p="xl" mb="lg"><Stack><Title order={2}>Verarbeitung und Vorschau</Title>
    {notice && <Alert role="status">{notice}</Alert>}
    {value && <><Checkbox label="Neue Originalvorschauen erlauben" checked={value.preview_enabled} disabled={!value.can_edit || busy} onChange={e => setValue({ ...value, preview_enabled: e.currentTarget.checked })} />
      <Checkbox label="Neue technische Wiederholungen erlauben" checked={value.retry_enabled} disabled={!value.can_edit || busy} onChange={e => setValue({ ...value, retry_enabled: e.currentTarget.checked })} />
      <Text size="sm" c="dimmed">Bereits freigegebene Wiederholungen bleiben als Aufträge erhalten. Diese Einstellungen aktivieren keinen automatischen Import.</Text>
      {value.can_edit && <Button onClick={save} loading={busy} style={{ alignSelf: "flex-start" }}>Verarbeitungseinstellungen speichern</Button>}
    </>}
  </Stack></Paper>;
}