"""
Testes unitários e de validação de efeito real para pdf.nup_booklet.
"""
from pathlib import Path
import pypdf
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.nup_booklet.logic import (
    calculate_booklet_order,
    process_nup_or_booklet,
)


def _create_4page_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))
    for i in range(1, 5):
        c.drawString(100, 750, f"Esta é a Página {i} original")
        c.showPage()
    c.save()


def test_calculate_booklet_order():
    """Testa sequência matemática de páginas para livreto dobrado."""
    # Para 4 páginas:
    # Folha 1 Frente: p4, p1
    # Folha 1 Verso: p2, p3
    assert calculate_booklet_order(4) == [4, 1, 2, 3]

    # Para 3 páginas (deve preencher a 4ª com None em branco)
    assert calculate_booklet_order(3) == [None, 1, 2, 3]


def test_nup_2up(tmp_path: Path):
    """Testa conversão de 4 páginas em 2 folhas com 2 páginas cada (2-Up)."""
    pdf_in = tmp_path / "4paginas.pdf"
    pdf_out = tmp_path / "2up.pdf"

    _create_4page_pdf(pdf_in)

    res = process_nup_or_booklet(pdf_in, pdf_out, mode="2UP")
    assert res.is_file()

    # Validação física do arquivo gerado
    reader = pypdf.PdfReader(res)
    assert len(reader.pages) == 2

    # Verifica dimensões: a página gerada é A4 Paisagem (width=841.89, height=595.27)
    box = reader.pages[0].mediabox
    assert round(float(box.width), 1) == 841.9
    assert round(float(box.height), 1) == 595.3


def test_nup_4up(tmp_path: Path):
    """Testa conversão de 4 páginas em 1 folha única em grade 2x2 (4-Up)."""
    pdf_in = tmp_path / "4paginas_4up.pdf"
    pdf_out = tmp_path / "4up.pdf"

    _create_4page_pdf(pdf_in)

    res = process_nup_or_booklet(pdf_in, pdf_out, mode="4UP")
    assert res.is_file()

    reader = pypdf.PdfReader(res)
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert round(float(box.width), 1) == 595.3
    assert round(float(box.height), 1) == 841.9
