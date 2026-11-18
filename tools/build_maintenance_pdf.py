"""Build only the separate AP10 supplement using the existing document renderer."""
import hashlib
import importlib.util
import json
from pathlib import Path

from reportlab.platypus import PageBreak,Paragraph,Spacer

ROOT=Path(__file__).resolve().parents[1]
specification=importlib.util.spec_from_file_location('technical_renderer',ROOT/'tools/build_technical_pdf.py')
renderer=importlib.util.module_from_spec(specification)
specification.loader.exec_module(renderer)


class MaintenanceDocument(renderer.Document):
    def __init__(self,output,title):
        super().__init__(output,title)
        self.subject='Wartungsnachtrag für Nutzer und Betreiber / AP10'

    def decorate(self,canvas,document):
        canvas.saveState()
        canvas.setStrokeColor(renderer.colors.HexColor('#C8D6DE'))
        canvas.line(renderer.MARGIN,38,renderer.WIDTH-renderer.MARGIN,38)
        canvas.setFont('Vera',7.5)
        canvas.setFillColor(renderer.INK)
        canvas.drawString(renderer.MARGIN,25,'AP10 | Dokumentstand 18.11.2026')
        canvas.drawRightString(renderer.WIDTH-renderer.MARGIN,25,'Seite '+str(document.page))
        if document.page>1:
            canvas.setFillColor(renderer.BLUE)
            canvas.drawString(renderer.MARGIN,renderer.HEIGHT-31,self.document_title)
        canvas.restoreState()


def main():
    source=ROOT/'docs/WARTUNGSNACHTRAG.md'
    output=ROOT/'docs/handbuecher/Wartungsnachtrag.pdf'
    renderer.SOURCE_PATH=source
    renderer.register_fonts()
    raw=source.read_bytes();lines=raw.decode('utf-8').splitlines()
    title=lines[0].removeprefix('# ')
    style=renderer.styles()
    story=[Paragraph(renderer.inline(title),style['title']),Spacer(1,6)]
    for flowable in renderer.parse(lines[1:],style):
        if isinstance(flowable,Paragraph) and flowable.style.name=='Section' and flowable.getPlainText() in {
                'Nachkontrolle und Störungen','Geprüfter Stand, Sicherung und offene Nachweise'}:
            story.append(PageBreak())
        story.append(flowable)
    document=MaintenanceDocument(output,title)
    document.multiBuild(story)
    assert 2<=document.page<=3
    print(json.dumps(dict(pages=document.page,reportlab=renderer.reportlab.Version,
        source_sha256=hashlib.sha256(raw).hexdigest(),pdf_sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2))


if __name__=='__main__': main()
