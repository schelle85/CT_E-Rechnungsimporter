"""Local bounded OCR of whole rendered pages; never rewrite the source PDF."""
import csv
from io import StringIO
import math
from pathlib import Path
import resource
import subprocess
import tempfile

from classifier.model import RecognitionError

DPI = 200
MAX_PAGE_PIXELS = 8_000_000
MAX_TOTAL_PIXELS = 40_000_000
MAX_OCR_PAGES = 10
MAX_OCR_BYTES = 2 * 1024 * 1024
MAX_PAGE_TEXT = 50000
OCR_SECONDS = 20
TESSERACT = "/usr/bin/tesseract"
TESSDATA = Path("/usr/share/tesseract-ocr/5/tessdata")


def ocr_limits():
    # The worker permits larger PNGs; the OCR output has a separate hard limit.
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OCR_BYTES,) * 2)


def read_tsv(raw):
    if len(raw) >= MAX_OCR_BYTES:
        raise RecognitionError("ocr_output_limit")
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8", errors="strict")), delimiter="\t", quoting=csv.QUOTE_NONE)
        if reader.fieldnames != ["level", "page_num", "block_num", "par_num", "line_num", "word_num",
                                 "left", "top", "width", "height", "conf", "text"]:
            raise ValueError()
        lines, words, size, weighted, letters, weak = [], [], 0, 0.0, 0, 0
        previous = None
        for row in reader:
            if row["level"] != "5":
                continue
            text = row["text"]
            confidence = float(row["conf"])
            if not math.isfinite(confidence) or not 0 <= confidence <= 100 or text is None:
                raise ValueError()
            key = tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num"))
            size += len(text) + 1
            if size > MAX_PAGE_TEXT:
                raise RecognitionError("text_size_limit")
            if previous is not None and key != previous:
                lines.append(" ".join(words))
                words = []
            previous = key
            words.append(text)
            count = sum(c.isalnum() for c in text)
            letters += count
            weighted += confidence * count
            weak += count if confidence < 40 else 0
        if words:
            lines.append(" ".join(words))
        # OCR engine confidence is a quality gate, never an invoice probability.
        if letters < 12 or weighted / letters < 55 or weak > letters / 4:
            raise RecognitionError("ocr_unreadable")
        return "\n".join(lines)
    except RecognitionError:
        raise
    except (ValueError, KeyError, TypeError, csv.Error):
        raise RecognitionError("ocr_output_invalid") from None


def image_text(image_path, directory):
    if not all((TESSDATA / (language + ".traineddata")).is_file() for language in ("deu", "eng", "osd")):
        raise RecognitionError("ocr_model_missing")
    output = directory / "output.tsv"
    try:
        with output.open("w+b") as stream:
            process = subprocess.Popen(
                [TESSERACT, str(image_path), "stdout", "--tessdata-dir", str(TESSDATA),
                 "-l", "deu+eng", "--psm", "1", "--dpi", str(DPI), "tsv"],
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.DEVNULL,
                cwd=directory, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "OMP_THREAD_LIMIT": "1"},
                preexec_fn=ocr_limits,
            )
            try:
                process.wait(timeout=OCR_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RecognitionError("ocr_timeout") from None
            stream.seek(0)
            raw = stream.read(MAX_OCR_BYTES)
            if len(raw) >= MAX_OCR_BYTES:
                raise RecognitionError("ocr_output_limit")
            if process.returncode != 0:
                raise RecognitionError("ocr_engine_failure")
            return read_tsv(raw)
    except RecognitionError:
        raise
    except OSError:
        raise RecognitionError("ocr_unavailable") from None


def complete_pages(document, pages, usable, max_text):
    pending = [i for i, text in enumerate(pages) if not usable(text)]
    if not pending:
        return pages, "pdf_text"
    if len(pending) > MAX_OCR_PAGES:
        raise RecognitionError("ocr_page_limit")
    total = 0
    for index in pending:
        page = document[index]
        try:
            width, height = page.get_size()
            if not all(math.isfinite(v) and 0 < v <= 10000 for v in (width, height)):
                raise RecognitionError("ocr_pixel_limit")
            pixels = math.ceil(width * DPI / 72) * math.ceil(height * DPI / 72)
            total += pixels
            if pixels > MAX_PAGE_PIXELS or total > MAX_TOTAL_PIXELS:
                raise RecognitionError("ocr_pixel_limit")
        finally:
            page.close()
    for index in pending:
        page = document[index]
        try:
            bitmap = page.render(scale=DPI / 72, grayscale=True, may_draw_forms=False, limit_image_cache=True)
            try:
                if bitmap.width * bitmap.height > MAX_PAGE_PIXELS:
                    raise RecognitionError("ocr_pixel_limit")
                with tempfile.TemporaryDirectory(prefix="ocr-") as temporary:
                    directory = Path(temporary)
                    image = bitmap.to_pil()
                    try:
                        image.save(directory / "page.png", format="PNG")
                    finally:
                        image.close()
                    pages[index] = image_text(directory / "page.png", directory)
                    if not usable(pages[index]):
                        raise RecognitionError("ocr_unreadable")
                    if sum(len(text) for text in pages) > max_text:
                        raise RecognitionError("text_size_limit")
            finally:
                bitmap.close()
        finally:
            page.close()
    return pages, "ocr" if len(pending) == len(pages) else "pdf_text_ocr"
