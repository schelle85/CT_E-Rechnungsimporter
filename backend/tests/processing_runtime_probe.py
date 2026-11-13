"""Synthetic two-role runtime probe; invoke only in a private network-none test container.
No customer sources/configuration, no production mount gate override, no runtime route.
"""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import httpx
import sqlalchemy as sa
from PIL import Image, ImageDraw, ImageFont
from app.graph import GraphClient
from app.graph_actions import GraphActions
from app.graph_state import ActionStore, metadata as graph_metadata
from app.processing import GraphProcessing, ProcessingService
from app.processing_cli import arguments
from app.processing_state import ProcessingStore, metadata as processing_metadata
from app.storage_state import StorageStore, metadata as storage_metadata
from app.storage_files import CifsFiles, parse_mounts, _parts
from test_graph import CONFIG, Credential
from test_graph_actions import ActionRemote
from test_graph_mail import attachment, message
from test_processing import PathFiles

CASE = Path("/case")


def save(value):
    temporary = CASE / "state.tmp"
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(CASE / "state.json")


def scan_pdf():
    # Same synthetic invoice evidence as the frozen AP03 test; Pillow makes an image-only PDF.
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    lines = ["Beispiel Lieferant GmbH", "Rechnung Nr. SYN-2026-001", "Rechnungsdatum: 12.11.2026",
             "Artikel und Leistungen", "Nettobetrag: 100,00 EUR", "Umsatzsteuer 19%: 19,00 EUR",
             "Gesamtbetrag: 119,00 EUR", "Zahlungsziel 14 Tage",
             "Die vereinbarte Lieferung umfasst Materialien und Leistungen.",
             "Bitte geben Sie bei Zahlungen die genannte Rechnungsnummer an."]
    for index, line in enumerate(lines):
        draw.text((90, 120 + index*70), line, font=font, fill="black")
    result = BytesIO()
    image.save(result, format="PDF", resolution=200.0)
    return result.getvalue()


def initialize():
    assert not (CASE / "state.json").exists() and not (CASE / "state.sqlite").exists()
    documents = [Path("/reference/ubl.xml").read_bytes(), scan_pdf(), b"synthetic-inline-signature"]
    names, types = ["invoice.xml", "scan.pdf", "logo.png"], ["application/xml", "application/pdf", "image/png"]
    rows = []
    for index, raw in enumerate(documents):
        aid = "a" + str(index)
        (CASE / aid).write_bytes(raw)
        row = attachment(aid, name=names[index], size=len(raw), inline=index == 2)
        row["contentType"] = types[index]
        rows.append(row)
    value = {"messages": {"m1": message(mid="m1")}, "attachments": {"m1": rows},
             "folders": {}, "stages": {}, "targets": {}, "published": [], "writes": 0, "downloads": 0}
    return value


def main():
    command = sys.argv[1]
    value = initialize() if command == "init" else json.loads((CASE / "state.json").read_text(encoding="utf-8"))
    engine = sa.create_engine("sqlite:////case/state.sqlite")
    for metadata in (processing_metadata, storage_metadata, graph_metadata):
        metadata.create_all(engine)
    remote = ActionRemote()
    remote.messages, remote.attachments, remote.folders = value["messages"], value["attachments"], value["folders"]
    def respond(request):
        if request.url.path.endswith("/mailFolders/inbox/messages"):
            return httpx.Response(200, json={"value": [item for item in remote.messages.values() if item["parentFolderId"] == "inbox"]})
        if request.url.path.endswith("/$value"):
            aid = request.url.path.split("/")[-2]
            return httpx.Response(200, content=(CASE / aid).read_bytes())
    remote.override = respond
    cifs_source = os.environ.get("AP05_CIFS_SMOKE_SOURCE")
    if cifs_source:
        # Only an operator-created exclusive Test/AP05-UUID bind; never production categories.
        files = CifsFiles("/destination", cifs_source, "_staging", staging_excluded=True)
        mount = parse_mounts(Path("/proc/self/mountinfo").read_text())[files.identity[0]]
        if mount["point"] != "/destination" or not re.fullmatch(r"/Test/AP05-[0-9a-f]{32}", mount["root"]):
            raise ValueError("exclusive_test_bind_required")
        if command == "init" and any(Path("/destination").iterdir()):
            raise ValueError("exclusive_test_bind_not_empty")
    else:
        files = PathFiles()
        files.stages = {name: base64.b64decode(data) for name,data in value["stages"].items()}
        files.targets = {name: base64.b64decode(data) for name,data in value["targets"].items()}
        files.published = value["published"]
    store = ProcessingStore(engine)
    with httpx.Client(transport=httpx.MockTransport(remote), trust_env=False) as http:
        client = GraphClient(CONFIG, Credential(), http, sleep=lambda _: None)
        service = ProcessingService(store, GraphProcessing(client, GraphActions(client, ActionStore(engine))),
                                    StorageStore(engine, destination_key=files.destination_key), files, "synthetic-runtime")
        if command == "init":
            key = service.scan()[0]
            value["key"] = key
            result = {"ok": True, "message_key": key}
        elif command == "advance":
            args = arguments(sys.argv[1:])
            finding = json.loads(Path(args.finding).read_text()) if args.finding else None
            result = {"ok": True, **service.advance(args.message_key, "/exchange", owner=args.owner, revision=args.revision,
                       attachment_key=args.attachment_key, finding=finding).result()}
        elif command == "verify":
            key = value["key"]
            rows = store.get_attachments(key)
            findings = [json.loads(row["original_finding"]) for row in rows]
            assert store.get_message(key)["state"] == "done"
            assert sorted(row["storage_state"] or "" for row in rows) == ["", "stored", "stored"]
            assert sum(row["signature"] for row in rows) == 1
            assert any(finding.get("method") == "ocr" and finding["category"] == "PDF" for finding in findings)
            assert any(finding["category"] == "E-Rechnung" for finding in findings)
            assert remote.messages["m1"]["parentFolderId"] == "folder-Nachfragen"
            assert remote.messages["m1"]["flag"]["flagStatus"] == "flagged"
            published = [row for row in rows if row["storage_state"] == "stored"]
            assert len(published) == 2
            if cifs_source:
                receipts = []
                for row in published:
                    receipt = service.storage.get(row["effect_key"])
                    request = store.storage_request(store.get_message(key), row, "synthetic-runtime")
                    assert receipt["publication_attempts"] == 1 and files.matches(row["storage_target"], request)
                    receipts.append({"action_key": row["effect_key"], "original_sha256": row["raw_sha256"],
                                     "byte_size": row["byte_size"], "publication_attempts": 1})
                # Simulate DMS consumption only for the two just verified synthetic test receipts.
                for row in published:
                    parts = _parts(row["storage_target"])
                    with files._directory(parts[:-1]) as parent:
                        files.guard()
                        os.unlink(parts[-1], dir_fd=parent)
                        os.fsync(parent)
            else:
                assert len(files.published) == 2
                receipts = []
                files.targets.clear()
            # A later idle step after source/DMS consumption cannot publish again.
            remote.attachments["m1"] = []
            result = {"ok": True, "stored": 2, "inline_exception": 1, "ocr": True, "target": "Nachfragen",
                      "post_move_flag": True, "published": 2, "cifs": bool(cifs_source), "receipts": receipts}
        else:
            raise ValueError()
    if not cifs_source:
        value.update(stages={name:base64.b64encode(data).decode() for name,data in files.stages.items()},
                     targets={name:base64.b64encode(data).decode() for name,data in files.targets.items()},
                     published=files.published)
    value.update(messages=remote.messages, attachments=remote.attachments, folders=remote.folders,
                 writes=value["writes"]+len(remote.writes),
                 downloads=value["downloads"]+sum(call.url.path.endswith("/$value") for call in remote.calls))
    save(value)
    if cifs_source:
        files.close()
    engine.dispose()
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"ok": False, "code": getattr(error, "code", "synthetic_probe_failed"),
                          "error_type": type(error).__name__}))
        raise SystemExit(1)
