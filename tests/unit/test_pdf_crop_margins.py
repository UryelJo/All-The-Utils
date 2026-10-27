"""
Testes unitários e de validação de efeito real para pdf.crop_margins.
"""
from pathlib import Path
import pypdf
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.crop_margins.logic import crop_pdf_document


def _create_centered_small_text_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))  # A4
    # Desenha texto concentrado no centro da página
    c.drawString(250, 420, "Texto Centralizado")
    c.save()


def test_crop_margins_manual(tmp_path: Path):
    """Testa aplicação de corte manual de margens fixas."""
    pdf_in = tmp_path / "original.pdf"
    pdf_out = tmp_path / "cortado_manual.pdf"

    _create_centered_small_text_pdf(pdf_in)

    crop_pdf_document(
        input_pdf_path=pdf_in,
        output_pdf_path=pdf_out,
        auto_crop=False,
        margin_left_pt=50.0,
        margin_bottom_pt=50.0,
        margin_right_pt=50.0,
        margin_top_pt=50.0,
    )

    assert pdf_out.is_file()
    reader = pypdf.PdfReader(pdf_out)
    page = reader.pages[0]

    # Mediabox original permanece inalterada
    assert round(float(page.mediabox.width), 1) == 595.3

    # Cropbox foi reduzida exatamente em 50pt de cada lado
    crop = page.cropbox
    assert round(float(crop.lower_left[0]), 1) == 50.0
    assert round(float(crop.lower_left[1]), 1) == 50.0
    assert round(float(crop.upper_right[0]), 1) == 545.3
    assert round(float(crop.upper_right[1]), 1) == 791.9


def test_crop_margins_auto(tmp_path: Path):
    """Testa detecção e corte automático de bordas brancas vazias."""
    pdf_in = tmp_path / "original_auto.pdf"
    pdf_out = tmp_path / "cortado_auto.pdf"

    _create_centered_small_text_pdf(pdf_in)

    crop_pdf_document(
        input_pdf_path=pdf_in,
        output_pdf_path=pdf_out,
        auto_crop=True,
        padding_pt=15.0,
    )

    assert pdf_out.is_file()
    reader = pypdf.PdfReader(pdf_out)
    page = reader.pages[0]
    crop = page.cropbox

    # A largura da cropbox deve ser muito menor que os 595.3pt da página inteira
    crop_w = float(crop.upper_right[0]) - float(crop.lower_left[0])
    crop_h = float(crop.upper_right[1]) - float(crop.lower_left[1])

    assert crop_w < 300.0  # O texto tem apenas ~100pt de largura + padding
    assert crop_h < 100.0
