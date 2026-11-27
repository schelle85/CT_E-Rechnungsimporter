"""Synthetic pure rendering contracts; no transport, credentials or customer data."""
from datetime import datetime
from html.parser import HTMLParser
import unittest
from unittest.mock import patch

from app import notification_model as model

NOW = 1795773600
KEY = "a" * 64
ORIGIN = "https://portal.example.invalid"
CONFIG = dict(model.DEFAULTS, recipients=["operator@example.invalid"])


def example(kind):
    slot = model.Slot(kind, NOW-86400, NOW, NOW, NOW+86400)
    if kind in {"daily", "weekly"}:
        slot = model.calendar_slot(kind, NOW, CONFIG)
        data = dict.fromkeys(model.REPORT_FIELDS, 0)
        data.update(messages=4, attachments=6, stored_receipts=3, unknown_open=1)
    elif kind == "certificate":
        data = dict(fingerprint="b"*64, expires_at=NOW+86400, remaining_seconds=86400)
    elif kind == "test":
        data = {}
    else:
        data = dict(source="processing", first_seen=NOW-1800, last_seen=NOW-60,
                    count=2, codes=["malformed_pdf"] if kind == "errors" else ["processing_source_unavailable"])
    return slot, data


class Document(HTMLParser):
    def __init__(self, content):
        super().__init__();self.tags=[];self.links=[];self.text=[]
        self.feed(content)
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "a":self.links.append(dict(attrs)["href"])
        assert not any(key.lower().startswith("on") for key, _ in attrs)
    def handle_data(self, data):self.text.append(data)


class TemplateTests(unittest.TestCase):
    def payload(self, kind, **kwargs):
        slot, data = example(kind)
        return model.make_payload(slot, KEY, CONFIG, data, NOW, **kwargs)

    def test_all_seven_kinds_use_same_frame_and_preserve_envelope(self):
        self.assertEqual(model.KINDS, {"certificate", "daily", "weekly", "errors", "outage", "recovery", "test"})
        for kind in sorted(model.KINDS):
            with self.subTest(kind=kind):
                payload = self.payload(kind, origin=ORIGIN);message=payload["message"]
                self.assertEqual(message["subject"], "E-Rechnungsimporter – "+model.SUBJECTS[kind])
                self.assertEqual(message["toRecipients"], [dict(emailAddress=dict(address=CONFIG["recipients"][0]))])
                self.assertIs(payload["saveToSentItems"], True)
                self.assertEqual(message["body"]["contentType"], "HTML")
                headers={row["name"]:row["value"] for row in message["internetMessageHeaders"]}
                self.assertEqual(headers, {"x-importer-notification-key":KEY,
                    "x-importer-template-version":"ap07-3"})
                content=message["body"]["content"];doc=Document(content)
                self.assertEqual(doc.links,[ORIGIN]);self.assertNotIn("script",doc.tags)
                self.assertIn('bgcolor="#073b50"',content);self.assertIn('<!--[if mso]>',content)
                text="".join(doc.text)
                self.assertEqual(text.count("Auftrag:"),1);self.assertEqual(text.count(KEY),1)
                self.assertEqual(text.count("Stand:"),1)
                self.assertIn(datetime.fromtimestamp(NOW,model.BERLIN).isoformat(sep=" "),text)
                self.assertLessEqual(len(model.canonical(payload)),16384)

    def test_incidents_keep_source_codes_counts_and_both_observation_times(self):
        for kind in ("errors","outage","recovery"):
            slot,data=example(kind)
            for source in ("api","graph","processing"):
                data["source"]=source
                content=model.make_payload(slot,KEY,CONFIG,data,NOW)["message"]["body"]["content"]
                text="".join(Document(content).text)
                for value in (source,*data["codes"],"Beobachtete Ereignisse: 2",
                    datetime.fromtimestamp(data["first_seen"],model.BERLIN).isoformat(),
                    datetime.fromtimestamp(data["last_seen"],model.BERLIN).isoformat()):self.assertIn(value,text)

    def test_certificate_and_test_keep_all_existing_facts_and_limits(self):
        text="".join(Document(self.payload("certificate")["message"]["body"]["content"]).text)
        for value in ("b"*64,"86400",datetime.fromtimestamp(NOW+86400,model.BERLIN).isoformat(),
                      "Warnserie endet erst nach geprüfter Anmeldung"):self.assertIn(value,text)
        text="".join(Document(self.payload("test")["message"]["body"]["content"]).text)
        self.assertIn("keine Rechnungs- oder Mailinhalte",text)
        self.assertIn("bestätigt noch keinen Empfang",text)

    def test_long_fingerprint_and_maximum_valid_code_keep_full_text_in_wrapping_body(self):
        for kind in ("certificate", "errors"):
            slot,data=example(kind)
            value="b"*64 if kind=="certificate" else "processing_"+"x"*53
            if kind=="errors":data["codes"]=[value]
            content=model.make_payload(slot,KEY,CONFIG,data,NOW)["message"]["body"]["content"]
            self.assertEqual(len(value),64)
            self.assertIn(value,"".join(Document(content).text))
            self.assertIn("max-width:600px;table-layout:fixed",content)
            self.assertIn('style="padding:16px 18px;overflow-wrap:anywhere;word-wrap:break-word"',content)

    def test_report_sections_counts_and_exclusive_period_remain(self):
        for kind in ("daily","weekly"):
            slot,data=example(kind);content=self.payload(kind)["message"]["body"]["content"]
            self.assertEqual(content.count('scope="row"'),len(model.REPORT_FIELDS))
            self.assertIn("bis ausschließlich",content)
            for instant in (slot.start,slot.end):self.assertIn(datetime.fromtimestamp(instant,model.BERLIN).isoformat(sep=" "),content)
            for heading,_ in model.REPORT_SECTIONS:self.assertIn(heading,content)

    def test_dynamic_title_and_origin_cannot_create_markup_or_attributes(self):
        title='<script>alert("x")</script> & Hinweis'
        origin='https://example.invalid"><img src=x onerror=alert(1)>'
        for kind in model.KINDS:
            with patch.dict(model.SUBJECTS,{kind:title}):
                content=self.payload(kind,origin=origin)["message"]["body"]["content"]
            doc=Document(content)
            self.assertNotIn("script",doc.tags);self.assertNotIn("img",doc.tags)
            self.assertEqual(doc.links,[origin]);self.assertIn(title,"".join(doc.text))
            self.assertIn("&lt;script&gt;",content)

    def test_origin_absence_and_existing_rejections_and_payload_limit_remain(self):
        for kind in model.KINDS:self.assertEqual(Document(self.payload(kind)["message"]["body"]["content"]).links,[])
        for origin in ("http://example.invalid","javascript:alert(1)",ORIGIN+"/other",ORIGIN+"?x=1",ORIGIN+"#x","https://user:pass@example.invalid"):
            with self.assertRaises(model.NotificationError):self.payload("errors",origin=origin)
        slot,data=example("errors");data["codes"]=['<img src=x>']
        with self.assertRaises(model.NotificationError):model.make_payload(slot,KEY,CONFIG,data,NOW)
        slot,data=example("daily");data=dict.fromkeys(data,10**1000)
        with self.assertRaisesRegex(model.NotificationError,"notification_payload_limit"):
            model.make_payload(slot,KEY,CONFIG,data,NOW)


if __name__=="__main__":unittest.main()
