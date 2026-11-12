"""Public synthetic fixtures; independent factur-x/pypdf generation, not the detector."""
from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, NameObject, TextStringObject
from facturx import generate_from_binary

REFERENCES = Path(__file__).parent / "references"


def plain_pdf(lines=("Synthetisches Testdokument",)):
    output = BytesIO()
    page = canvas.Canvas(output, pagesize=(595, 842), invariant=1)
    for index, text in enumerate(lines):
        page.drawString(40, 790 - 20 * index, text)
    page.showPage()
    page.save()
    return output.getvalue()


def text_document(pages):
    output = BytesIO()
    writer = canvas.Canvas(output, pagesize=(595, 842), invariant=1)
    for lines in pages:
        writer.setFont("Helvetica", 12)
        for index, line in enumerate(lines):
            writer.drawString(40, 790 - 20 * index, line)
        writer.showPage()
    writer.save()
    return output.getvalue()


def scan_document(pages, angle=0, dpi=200, blur=0):
    """Independent Pillow raster + reportlab PDF, without a text layer."""
    output = BytesIO()
    writer = canvas.Canvas(output, invariant=1)
    for lines in pages:
        width, height = round(595 * dpi / 72), round(842 * dpi / 72)
        image = Image.new("L", (width, height), 255)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(3, round(12 * dpi / 72)))
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((round(40 * dpi / 72), round((45 + index * 20) * dpi / 72)), line, font=font, fill=0)
        if blur:
            blurred = image.filter(ImageFilter.GaussianBlur(blur))
            image.close()
            image = blurred
        if angle:
            rotated = image.rotate(angle, expand=angle % 90 == 0, fillcolor=255)
            image.close()
            image = rotated
        try:
            size = (image.width * 72 / dpi, image.height * 72 / dpi)
            writer.setPageSize(size)
            writer.drawImage(ImageReader(image), 0, 0, width=size[0], height=size[1])
            writer.showPage()
        finally:
            image.close()
    writer.save()
    return output.getvalue()


def join_documents(*documents):
    writer = PdfWriter()
    for data in documents:
        writer.append(PdfReader(BytesIO(data)))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def reference_xml(name):
    return (REFERENCES / "facturx" / (name + ".xml")).read_bytes()


def hybrid(profile="en16931"):
    return generate_from_binary(plain_pdf(), reference_xml("factur-x-" + profile),
                               flavor="factur-x", level=profile, check_xsd=False, check_schematron=False)


def legacy_hybrid(profile="comfort"):
    # Separate pypdf writer uses the published legacy XML unchanged.
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(plain_pdf())))
    attachment = writer.add_attachment("ZUGFeRD-invoice.xml", reference_xml("zugferd-" + profile))
    attachment.associated_file_relationship = NameObject("/Alternative")
    writer._root_object[NameObject("/AF")] = ArrayObject([attachment.pdf_object.indirect_reference])
    xml = ("<?xpacket begin='\ufeff'?>"
           "<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
           "<rdf:Description xmlns:zf='urn:ferd:pdfa:CrossIndustryDocument:invoice:1p0#'>"
           "<zf:DocumentType>INVOICE</zf:DocumentType><zf:DocumentFileName>ZUGFeRD-invoice.xml</zf:DocumentFileName>"
           f"<zf:ConformanceLevel>{profile.upper()}</zf:ConformanceLevel><zf:Version>1.0</zf:Version>"
           "</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>").encode("utf-8")
    metadata = DecodedStreamObject()
    metadata.set_data(xml)
    metadata[NameObject("/Type")] = NameObject("/Metadata")
    metadata[NameObject("/Subtype")] = NameObject("/XML")
    writer._root_object[NameObject("/Metadata")] = writer._add_object(metadata)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
