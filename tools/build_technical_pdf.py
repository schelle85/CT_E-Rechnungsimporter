"""Render the AP09 Markdown documents with ReportLab only (no network access).

Supported subset: headings, paragraphs, flat lists, fenced text, pipe tables,
inline code/bold and links. This is a document renderer, not an application tool.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

import reportlab
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle, Image, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "docs/TECHNISCHE-DOKUMENTATION.md"
GITHUB = "https://github.com/schelle85/CT_E-Rechnungsimporter"
INK = colors.HexColor("#172A3A")
BLUE = colors.HexColor("#165C79")
PALE = colors.HexColor("#EDF3F6")
WIDTH, HEIGHT = A4
MARGIN = 46
CONTENT = WIDTH - 2 * MARGIN
rl_config.invariant = 1
HANDBOOK = False


def register_fonts():
    font_dir = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("Vera", "Vera.ttf"), ("Vera-Bold", "VeraBd.ttf"),
                           ("Vera-Italic", "VeraIt.ttf"), ("Vera-BoldItalic", "VeraBI.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(font_dir / filename)))
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="Vera-Bold",
                                italic="Vera-Italic", boldItalic="Vera-BoldItalic")


def pdf_link(target):
    """Resolve this repository's document links from the Markdown source location."""
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return target
    resolved = ((SOURCE_PATH.parent / unquote(parts.path)).resolve()
                if parts.path else SOURCE_PATH.resolve())
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError("Relative PDF link leaves the repository") from error
    kind = "tree" if resolved.is_dir() else "blob"
    result = f"{GITHUB}/{kind}/main/{quote(relative.as_posix(), safe='/')}"
    if parts.query:
        result += "?" + parts.query
    if parts.fragment:
        result += "#" + parts.fragment
    return result


def inline(value):
    # Protect inline tokens before XML escaping; code remains literal.
    tokens = []

    def hold(markup):
        tokens.append(markup)
        return f"TOKENPLACEHOLDER{len(tokens) - 1}END"

    value = re.sub(r"`([^`]+)`", lambda m: hold(
        '<font color="#344C60">' + html.escape(m[1]) + '</font>'), value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: hold(
        '<a href="' + html.escape(pdf_link(m[2]), quote=True) + '" color="#165C79">'
        + html.escape(m[1]) + '</a>'), value)
    value = html.escape(value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    for index, token in enumerate(tokens):
        value = value.replace(f"TOKENPLACEHOLDER{index}END", token)
    return value


class Document(BaseDocTemplate):
    def __init__(self, output, title, document_label=None):
        super().__init__(str(output), pagesize=A4, leftMargin=MARGIN,
                         rightMargin=MARGIN, topMargin=53, bottomMargin=48,
                         title=title, author="CT E-Rechnungsimporter",
                         subject="Nutzer- und Administrationshandbuch / AP11" if HANDBOOK else "Technische Betriebs- und Übergabeunterlage / AP09",
                         pageCompression=1, allowSplitting=1)
        self.document_title = title
        self.document_label = document_label if document_label is not None else (
            "AP11 | Dokumentstand 18.11.2026" if HANDBOOK else "AP09 | Dokumentstand 17.11.2026")
        self.addPageTemplates(PageTemplate(id="document", frames=[Frame(
            MARGIN, 48, CONTENT, HEIGHT - 101, leftPadding=0, rightPadding=0,
            topPadding=0, bottomPadding=0)], onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#C8D6DE"))
        canvas.line(MARGIN, 38, WIDTH - MARGIN, 38)
        canvas.setFont("Vera", 7.5)
        canvas.setFillColor(INK)
        canvas.drawString(MARGIN, 25, self.document_label)
        canvas.drawRightString(WIDTH - MARGIN, 25, str(doc.page))
        if doc.page > 1:
            canvas.setFillColor(BLUE)
            canvas.drawString(MARGIN, HEIGHT - 31, self.document_title)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "Section":
            title = flowable.getPlainText()
            key = "section-" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:14]
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=0, closed=False)
            self.notify("TOCEntry", (0, title, self.page, key))


def styles():
    body = ParagraphStyle("Body", fontName="Vera", fontSize=9.3, leading=14,
                          textColor=INK, spaceAfter=8, splitLongWords=True,
                          allowWidows=0, allowOrphans=0)
    if HANDBOOK:
        body.fontSize, body.leading = 10, 15
    return {
        "body": body,
        "title": ParagraphStyle("Title", parent=body, fontName="Vera-Bold",
                                fontSize=29, leading=35, textColor=BLUE, spaceAfter=20),
        "section": ParagraphStyle("Section", parent=body, fontName="Vera-Bold",
                                  fontSize=15, leading=20, textColor=BLUE,
                                  spaceBefore=18, spaceAfter=11, keepWithNext=True),
        "sub": ParagraphStyle("Sub", parent=body, fontName="Vera-Bold", fontSize=11,
                              leading=15, spaceBefore=10, keepWithNext=True),
        "cell": ParagraphStyle("Cell", parent=body, fontSize=8.1, leading=11.8,
                               spaceAfter=0, allowWidows=1, allowOrphans=1),
        "head": ParagraphStyle("Head", parent=body, fontName="Vera-Bold", fontSize=8.2,
                               leading=12, textColor=colors.white, spaceAfter=0),
        "code": ParagraphStyle("Code", parent=body, fontSize=8, leading=12,
                               backColor=PALE, borderPadding=9, spaceBefore=3,
                               spaceAfter=12),
        "list": ParagraphStyle("List", parent=body, leftIndent=13, firstLineIndent=-13,
                               spaceAfter=5),
        "caption": ParagraphStyle("Caption", parent=body, fontSize=8.2, leading=11,
                                  textColor=BLUE, spaceBefore=5, spaceAfter=12),
    }


def table(lines, style):
    rows = [[part.strip() for part in row.strip().strip("|").split("|")]
            for row in lines]
    if len(rows) < 2 or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        raise ValueError("Expected table separator row")
    rows.pop(1)
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise ValueError("Inconsistent table columns")
    data = [[Paragraph(inline(cell), style["head" if i == 0 else "cell"])
             for cell in row] for i, row in enumerate(rows)]
    widths = [CONTENT * .33, CONTENT * .67] if columns == 2 else [CONTENT / columns] * columns
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", spaceAfter=12)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5 if HANDBOOK else 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 if HANDBOOK else 7),
        ("LINEBELOW", (0, 0), (-1, 0), .4, BLUE),
    ]))
    return result


def make_story(source, title):
    if HANDBOOK:
        source = re.sub(r"<!-- toc:start -->.*?<!-- toc:end -->", "", source, flags=re.S)
    style = styles()
    lines = source.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("Document must begin with one level-1 title")
    story = [Spacer(1, 105), Paragraph(inline(title), style["title"])]
    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if first_section is None:
        raise ValueError("Document needs level-2 sections")
    # Cover contains the original introductory paragraphs without its title.
    story.extend(parse(lines[1:first_section], style))
    story.append(PageBreak())
    story.append(Paragraph("Inhaltsverzeichnis", style["title"]))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("TOC", fontName="Vera", fontSize=9.5,
                                      leading=17, spaceBefore=0, textColor=INK,
                                      rightIndent=20, alignment=TA_LEFT)]
    toc.tableStyle = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])
    story.extend([toc, PageBreak()])
    story.extend(parse(lines[first_section:], style))
    return story


def parse(lines, style):
    result, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("!["):
            match = re.fullmatch(r"!\[([^\]]+)\]\(([^)]+)\)", line)
            if not match:
                raise ValueError("Expected a standalone Markdown image")
            path = (SOURCE_PATH.parent / unquote(match[2])).resolve()
            if not path.is_relative_to(ROOT.resolve()) or path.suffix.lower() != ".png":
                raise ValueError("Only repository PNG illustrations are supported")
            picture = Image(str(path))
            height_limit = 420 if path.name == "06-zuordnung.png" else 320
            scale = min(1, CONTENT / picture.imageWidth, height_limit / picture.imageHeight)
            picture.drawWidth = picture.imageWidth * scale
            picture.drawHeight = picture.imageHeight * scale
            picture.hAlign = "LEFT"
            result.append(KeepTogether([picture, Paragraph(inline(match[1]), style["caption"])]))
            index += 1
            continue
        if line.startswith("```"):
            code = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(html.escape(lines[index]).replace(" ", "&#160;"))
                index += 1
            if index == len(lines):
                raise ValueError("Unclosed code fence")
            result.append(Paragraph("<br/>".join(code), style["code"]))
            index += 1
        elif line.startswith("|"):
            block = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index])
                index += 1
            result.append(table(block, style))
        elif line.startswith("## ") or line.startswith("### "):
            level = "section" if line.startswith("## ") else "sub"
            if HANDBOOK and level == "section" and result:
                result.append(PageBreak())
            result.append(Paragraph(inline(line.split(" ", 1)[1]), style[level]))
            index += 1
        elif line.startswith("#"):
            raise ValueError("Only one H1 and H2/H3 headings supported")
        else:
            bullet = re.match(r"^(?:- |(\d+)\. )", line)
            content = line[bullet.end():] if bullet else line
            index += 1
            while index < len(lines) and lines[index].strip():
                following = lines[index].strip()
                if following.startswith(("#", "|", "```", "- ", "![")) or re.match(r"\d+\. ", following):
                    break
                content += " " + following
                index += 1
            if bullet:
                prefix = (bullet[1] + ". ") if bullet[1] else "- "
                result.append(Paragraph(prefix + inline(content), style["list"]))
            else:
                paragraph = Paragraph(inline(content), style["body"])
                following = next((value.strip() for value in lines[index:] if value.strip()), "")
                if following.startswith(("- ", "```")) or re.match(r"\d+\. ", following):
                    paragraph.keepWithNext = True
                result.append(paragraph)
    return result


def main():
    global SOURCE_PATH, HANDBOOK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "docs/TECHNISCHE-DOKUMENTATION.md")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/handbuecher/Technische-Dokumentation.pdf")
    parser.add_argument("--handbook", action="store_true", help="AP11 page layout, figures and metadata")
    parser.add_argument("--document-label", help="Override the footer label; omission preserves the historical label")
    args = parser.parse_args()
    HANDBOOK = args.handbook
    SOURCE_PATH = args.input.resolve()
    source_bytes = args.input.read_bytes()
    source = source_bytes.decode("utf-8-sig")
    title = source.splitlines()[0].removeprefix("# ")
    register_fonts()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = Document(args.output, title, document_label=args.document_label)
    document.multiBuild(make_story(source, title))
    print(json.dumps({"pages": document.page, "reportlab": reportlab.Version,
                      "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                      "pdf_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
