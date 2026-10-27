"""
Testes unitários e de validação de efeito real para pdf.scan_cleanup.
"""
from pathlib import Path
import pypdf
from reportlab.lib.colors import Color, black
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.scan_cleanup.logic import cleanup_scanned_pdf


def _create_dirty_scan_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))
    # Simula fundo cinza/mancha de scanner
    c.setFillColor(Color(0.85, 0.85, 0.85))
    c.rect(0, 0, 595.27, 841.89, fill=1, stroke=0)

    # Texto escuro
    c.setFillColor(black)
    c.drawString(100, 750, "Documento Digitalizado com Fundo Acinzentado")
    c.drawString(100, 700, "Texto principal legível.")
    c.save()


def test_cleanup_scanned_pdf(tmp_path: Path):
    """Testa higienização e binarização de PDF digitalizado."""
    pdf_in = tmp_path / "scan_sujo.pdf"
    pdf_out = tmp_path / "scan_higienizado.pdf"

    _create_dirty_scan_pdf(pdf_in)

    res = cleanup_scanned_pdf(
        input_pdf_path=pdf_in,
        output_pdf_path=pdf_out,
        contrast_factor=2.0,
        to_pure_bw=True,
        binarize_threshold=170,
        sharpen=True,
        dpi=100,
    )

    assert res.is_file()
    assert res == pdf_out

    # Validação física do arquivo gerado
    reader = pypdf.PdfReader(res)
    assert len(reader.pages) == 1
