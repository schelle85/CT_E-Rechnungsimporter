type Finding = { status: string; reason: string; warnings?: string[] } | null;
const ambiguous = new Set(["ambiguous_pdf", "ambiguous_invoice", "ambiguous_payment_advice", "ambiguous_reminder", "ambiguous_mixed_document"]);

export function findingWarnings(value: Finding): string[] {
  const labels: Record<string, string> = {
    pdf_stream_missing_checksum: "PDF-Strukturprüfung: Ein vollständig lesbarer Datenstrom hat einen unvollständigen Prüfsummenabschluss. Die Originaldatei bleibt unverändert.",
    hybrid_xrechnung_metadata_version: "PDF-Metadaten: Die angegebene Hybridversion weicht ab. Die eingebettete XRechnung wurde anhand ihrer XML-Struktur erkannt. Das ist keine vollständige Konformitätsprüfung.",
  };
  return (value?.warnings ?? []).filter(code => Object.hasOwn(labels, code)).map(code => labels[code]);
}

export function recognitionText(value: Finding): string {
  if (!value) return "Ein aktueller Befund steht noch aus.";
  if (value.reason === "unsupported_invoice_profile") return "Bei der letzten Prüfung wurde dieses Rechnungsprofil nicht unterstützt.";
  if (value.reason === "ambiguous_mixed_document") return "Das PDF enthält Hinweise auf verschiedene Dokumentarten. Auch eine Bestellreferenz kann die Erkennung beeinflussen.";
  if (["malformed_xml", "malformed_invoice", "unsafe_xml", "unsupported_invoice_namespace"].includes(value.reason)) return "Die XML-Datei konnte nicht sicher als unterstützte Rechnung gelesen werden. Datei und Formatunterstützung müssen geprüft werden.";
  if (value.status === "failed") return "Der Abruf oder die technische Prüfung ist fehlgeschlagen.";
  if (value.status === "unknown") return ambiguous.has(value.reason)
    ? "Die Dokumentart ist nicht eindeutig. Bitte den Anhang im Original prüfen."
    : "Der Befund enthält einen Struktur- oder Formatkonflikt. Eine manuelle Zuordnung ist gesperrt.";
  return value.status === "recognized" ? "Die Dokumentart wurde erkannt." : "Der Anhang wurde gemäß dem protokollierten Befund ausgenommen.";
}

export function attachmentNextStep(value: Finding, canEdit: boolean, canCorrect: boolean): string {
  if (!value) return "Bitte den nächsten Verarbeitungsbefund abwarten.";
  if (value.reason === "unsupported_invoice_profile") return "Bitte die Betreuung informieren.";
  if (value.status === "unknown" && ambiguous.has(value.reason)) {
    if (!canEdit) return "Sie haben Leserechte. Bitte das Original prüfen und ein Verwaltungskonto um die Zuordnung bitten.";
    return canCorrect ? "Bitte das Original prüfen und nur bei eindeutiger Dokumentart die passende Zuordnung freigeben. Bei Zweifeln die Betreuung hinzuziehen."
      : "Die Zuordnung ist derzeit gesperrt. Bitte zuerst den Mailabschluss und die Vorgangshinweise klären lassen.";
  }
  if (value.status === "failed" || value.status === "unknown") return "Bitte das Original und den Befund mit der Betreuung prüfen. Eine Lieferantenkorrektur ist erst nach bestätigtem Dateifehler sinnvoll.";
  return "Bitte den Ablagebeleg und den getrennten Mailabschluss beachten.";
}

export function mailCompletionHint(errorCode: string | null, canEdit: boolean): string | null {
  if (errorCode !== "graph_existing_completed_flag") return null;
  return "Die Mail ist in Outlook bereits erledigt. Entscheiden Sie mit der zuständigen Person, ob die Markierung beibehalten oder in Outlook reaktiviert werden soll. Der Importer setzt sie nicht automatisch zurück. "
    + (canEdit ? "Bitte vor einer Wiederholung den bisherigen Mailabschluss mit der Betreuung prüfen."
      : "Sie haben Leserechte. Bitte ein Verwaltungskonto oder die Betreuung hinzuziehen.");
}
