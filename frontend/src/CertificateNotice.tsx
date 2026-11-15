import { useEffect, useRef, useState } from "react";
import { Alert, Button, Modal, Stack, Text } from "@mantine/core";
import { api } from "./api";
import { dateTime } from "./processTypes";

type Certificate = { fingerprint: string; expires_at: number; remaining_seconds: number; severity: "healthy" | "orange" | "red"; valid?: boolean };
export type CertificateStatus = { checked_at: number; local: Partial<Certificate> & { code?: string }; warning: Certificate | null; proof: { fingerprint: string; at: number } | null };
export default function CertificateNotice() {
  const [value, setValue] = useState<CertificateStatus | null>(null), [error, setError] = useState("");
  const [opened, setOpened] = useState(false); const initial = useRef(true);
  async function read() {
    try {
      const next = await api<CertificateStatus>("/api/notifications/certificate");
      setValue(next); setError("");
      if (initial.current && (next.warning || next.local.severity === "red" || next.local.severity === "orange")) setOpened(true);
      initial.current = false;
    } catch (e) { setValue(null); setError(e instanceof Error ? e.message : "Zertifikatsstatus nicht verfügbar."); }
  }
  useEffect(() => { void read(); const timer = setInterval(() => void read(), 60000); return () => clearInterval(timer); }, []);
  const warning = value?.warning || (value?.local.severity !== "healthy" ? value?.local : null);
  const body = <Stack gap="xs">
    {warning?.expires_at && <Text>Warnung für Graph-Anmeldezertifikat: Ablauf {dateTime(warning.expires_at)}. Restzeit {Math.floor((warning.remaining_seconds || 0) / 3600)} Stunden.</Text>}
    {value?.warning && <Text>Die gespeicherte Pflichtwarnung ist offen. Sie endet erst nach erfolgreicher frischer Graphanmeldung mit einem lokal gültigen Nachfolger. Ein Dateitausch genügt nicht.</Text>}
    {value?.local.expires_at ? <Text size="sm">Lokal gelesene Datei: Ablauf {dateTime(value.local.expires_at)} · Restzeit {Math.floor((value.local.remaining_seconds || 0) / 3600)} Stunden · {value.local.valid ? "derzeit gültig" : "derzeit nicht gültig"}. Dies ist kein neuer Graph-Anmeldenachweis.</Text> : <Text>Die lokale Zertifikatsdatei konnte nicht geprüft werden.</Text>}
    <Text size="sm">{value?.proof ? "Letzter gespeicherter erfolgreicher Graphnachweis: " + dateTime(value.proof.at) + "." : "Kein erfolgreicher Nachfolgernachweis gespeichert."}</Text>
    <Text size="sm">Das Graph-Anmeldezertifikat ist vom HTTPS-Zertifikat unabhängig. Bitte bei einer Warnung die Betreuung informieren.</Text>
  </Stack>;
  return <>
    {error ? <Alert color="yellow" mb="lg" title="Zertifikatsstatus nicht prüfbar">{error}<Button variant="subtle" size="xs" onClick={() => void read()}>Erneut prüfen</Button></Alert> : value && (warning || value.local.code) ? <Alert color={warning?.severity === "red" || value.local.severity === "red" ? "red" : "orange"} mb="lg" title="Graph-Zertifikat · Handlungsbedarf" role="alert">{body}<Button variant="subtle" size="xs" mt="xs" onClick={() => void read()}>Status aktualisieren</Button></Alert> : null}
    <Modal opened={opened} onClose={() => setOpened(false)} title="Zertifikatshinweis nach Anmeldung" centered size="lg">{body}<Button mt="lg" onClick={() => setOpened(false)}>Hinweis gelesen</Button></Modal>
  </>;
}
