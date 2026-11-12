from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

from classifier.cli import bounded_classify, child as real_child
from classifier.core import classify
from classifier.ocr import image_text
from fixtures import join_documents, scan_document, text_document
from test_text_pdf import AVIS, ENGLISH, INVOICE

BODY = ["Die vereinbarte Lieferung umfasst Materialien und Leistungen.",
        "Für Rückfragen stehen wir während unserer Geschäftszeiten bereit.",
        "Bitte geben Sie bei Zahlungen die genannte Rechnungsnummer an.",
        "Vielen Dank für die vertrauensvolle Zusammenarbeit und Ihre Aufträge."]


def instrumented_child(send, data, work_directory):
    import classifier.ocr as ocr
    ocr.TESSERACT = str(Path(__file__).with_name("ocr_timeout_probe.py"))
    real_child(send, data, work_directory)


def live(pid):
    try:
        # Zombies own no running engine or memory; --init reaps orphan descendants.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


class OcrTests(unittest.TestCase):
    def check_scan(self, data, category=None, reason=None, method=None):
        digest = sha256(data).hexdigest()
        result = classify(data)
        if category:
            self.assertEqual(result["status"], "recognized", result)
            self.assertEqual(result["category"], category, result)
        else:
            self.assertEqual(result["status"], "unknown" if reason and reason.startswith("ambiguous_") else "failed", result)
        if reason:
            self.assertEqual(result["reason"], reason, result)
        if method:
            self.assertEqual(result["method"], method, result)
        self.assertEqual(result["original_sha256"], digest)
        self.assertEqual(sha256(data).hexdigest(), digest)
        self.assertNotIn("SYN-2026", str(result))
        return result

    def test_actual_german_scan_umlauts_and_advice(self):
        self.check_scan(scan_document([INVOICE + BODY]), "PDF", method="ocr")
        self.check_scan(scan_document([AVIS + BODY]), "Zahlungsavis", method="ocr")

    def test_actual_english_scan(self):
        self.check_scan(scan_document([ENGLISH + BODY]), "PDF", method="ocr")

    def test_actual_quarter_turn_and_upside_down(self):
        for angle in (90, 180, 270):
            with self.subTest(angle=angle):
                self.check_scan(scan_document([INVOICE + BODY], angle=angle), "PDF", method="ocr")

    def test_actual_slight_skew(self):
        self.check_scan(scan_document([INVOICE + BODY], angle=3), "PDF", method="ocr")

    def test_mixed_pages_ocr_only_where_needed_and_detect_conflicts(self):
        data = join_documents(text_document([INVOICE]), scan_document([BODY]))
        with patch("classifier.ocr.image_text", wraps=image_text) as engine:
            self.check_scan(data, "PDF", method="pdf_text_ocr")
            self.assertEqual(engine.call_count, 1)
        conflict = join_documents(text_document([INVOICE]), scan_document([AVIS + BODY]))
        self.check_scan(conflict, reason="ambiguous_mixed_document")

    def test_clean_text_never_starts_ocr(self):
        with patch("classifier.ocr.image_text", side_effect=AssertionError("OCR must not run")):
            self.check_scan(text_document([INVOICE]), "PDF", method="pdf_text")

    def test_blank_and_degraded_low_resolution_never_succeed(self):
        self.check_scan(scan_document([[]]), reason="ocr_unreadable")
        self.check_scan(scan_document([INVOICE], dpi=25, blur=2))

    def test_missing_model_is_closed_and_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as parent:
            with patch("classifier.ocr.TESSDATA", Path(parent)), patch("tempfile.tempdir", parent):
                self.check_scan(scan_document([INVOICE]), reason="ocr_model_missing")
            self.assertEqual(list(Path(parent).iterdir()), [])

    def test_success_and_engine_failure_clean_temporary_files(self):
        with tempfile.TemporaryDirectory() as parent:
            with patch("tempfile.tempdir", parent):
                self.check_scan(scan_document([INVOICE + BODY]), "PDF")
                with patch("classifier.ocr.TESSERACT", "/not-installed"):
                    self.check_scan(scan_document([INVOICE]), reason="ocr_unavailable")
            self.assertEqual(list(Path(parent).iterdir()), [])

    def test_actual_engine_timeout_and_output_file_limit(self):
        with patch("classifier.ocr.OCR_SECONDS", 0.0001):
            self.check_scan(scan_document([INVOICE]), reason="ocr_timeout")
        with patch("classifier.ocr.TESSERACT", str(Path(__file__).with_name("ocr_output_probe.py"))):
            self.check_scan(scan_document([INVOICE]), reason="ocr_output_limit")

    def test_preflight_ocr_page_pixel_and_total_limits(self):
        data = scan_document([INVOICE])
        with patch("classifier.ocr.MAX_OCR_PAGES", 0):
            self.check_scan(data, reason="ocr_page_limit")
        with patch("classifier.ocr.MAX_PAGE_PIXELS", 10):
            self.check_scan(data, reason="ocr_pixel_limit")
        with patch("classifier.ocr.MAX_TOTAL_PIXELS", 10):
            self.check_scan(data, reason="ocr_pixel_limit")
        self.check_scan(scan_document([[]] * 11), reason="ocr_page_limit")

    def test_actual_fixed_pixel_limits_without_rendering_huge_pages(self):
        for count, width, height in ((1, 4000, 4000), (7, 800, 1000)):
            writer = PdfWriter()
            writer.append(PdfReader(BytesIO(text_document([[]] * count))))
            for page in writer.pages:
                page.mediabox = RectangleObject([0, 0, width, height])
            output = BytesIO()
            writer.write(output)
            with patch("pypdfium2.PdfPage.render", side_effect=AssertionError("must fail before rendering")):
                self.check_scan(output.getvalue(), reason="ocr_pixel_limit")

    def test_actual_ocr_text_limit(self):
        with patch("classifier.ocr.MAX_PAGE_TEXT", 20):
            self.check_scan(scan_document([INVOICE + BODY]), reason="text_size_limit")

    def test_real_bounded_worker_with_ocr(self):
        data = scan_document([INVOICE + BODY])
        result = bounded_classify(data)
        self.assertEqual(result["status"], "recognized", result)
        self.assertEqual(result["method"], "ocr", result)
        self.assertEqual(result["original_sha256"], sha256(data).hexdigest())

    def test_document_timeout_kills_actual_ocr_and_descendants_and_cleans(self):
        data = scan_document([INVOICE + BODY])
        roots_before = set(Path(tempfile.gettempdir()).glob("ct-classifier-*"))
        observed, stop = set(), threading.Event()
        def observe():
            while not stop.wait(0.01):
                for root in set(Path(tempfile.gettempdir()).glob("ct-classifier-*")) - roots_before:
                    for record in root.glob("ocr-*/probe-pids.json"):
                        try:
                            observed.update(json.loads(record.read_text()))
                        except (FileNotFoundError, json.JSONDecodeError):
                            pass
        observer = threading.Thread(target=observe)
        observer.start()
        try:
            with patch("classifier.cli.child", instrumented_child):
                result = bounded_classify(data, seconds=2)
        finally:
            stop.set()
            observer.join()
        self.assertEqual(result["reason"], "document_timeout", result)
        self.assertEqual(len(observed), 2, "real OCR and hanging descendant must both have started")
        for _ in range(30):
            if not any(live(pid) for pid in observed):
                break
            time.sleep(0.01)
        self.assertFalse(any(live(pid) for pid in observed))
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("ct-classifier-*")), roots_before)
        self.assertEqual(result["original_sha256"], sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
