"""Only synthetic fixtures. No message, attachment or document operations."""
ITEMS = [
    dict(id="DEMO-1005",received="08.11.2026 · 14:42",sender="Beispiel Metallhandel",subject="Musterrechnung November",category="E-Rechnung",status="Erfolgreich",filename="musterrechnung-105.xml",reason="Beispiel: als XRechnung erkannt und abgelegt.",size="24 KB"),
    dict(id="DEMO-1004",received="08.11.2026 · 14:28",sender="Demo Bürobedarf",subject="Ihre Beispielrechnung",category="PDF",status="Prüfen",filename="beispiel-104.pdf",reason="Beispiel: gewöhnliche PDF-Rechnung, fachliche Prüfung vorgesehen.",size="182 KB"),
    dict(id="DEMO-1003",received="08.11.2026 · 13:51",sender="Muster Servicebetrieb",subject="Beleg zur Beispielbestellung",category="Unklar",status="Fehler",filename="musterbeleg-103.pdf",reason="Beispiel: Inhalt nicht eindeutig lesbar.",size="91 KB"),
    dict(id="DEMO-1002",received="08.11.2026 · 13:10",sender="Beispiel Metallhandel",subject="Rechnung erneut gesendet",category="E-Rechnung",status="Dublette",filename="musterrechnung-102.xml",reason="Beispiel: gleicher Originalname und gleiche Größe in derselben Kalenderwoche.",size="22 KB"),
    dict(id="DEMO-1001",received="08.11.2026 · 12:35",sender="Demo Handelspartner",subject="Zahlungsavis – Muster",category="Zahlungsavis",status="Erfolgreich",filename="musteravis-101.pdf",reason="Beispiel: als Zahlungsavis erkannt und abgelegt.",size="68 KB"),
]
