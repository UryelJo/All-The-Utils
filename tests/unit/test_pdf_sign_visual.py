"""
Testes unitários e de validação de efeito real para pdf.sign_visual.
"""
from pathlib import Path
from PIL import Image
import pypdf
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.sign_visual.logic import apply_visual_signature


def _create_sample_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))  # A4
    c.drawString(100, 750, "Contrato de Prestação de Serviços")
    c.drawString(100, 700, "Primeira página do documento.")
    c.showPage()
    c.drawString(100, 750, "Segunda página do documento.")
    c.drawString(100, 700, "Assine aqui:")
    c.save()


def _create_signature_png(path: Path) -> None:
    # Imagem RGBA transparente de 200x80
    img = Image.new("RGBA", (200, 80), (0, 0, 0, 0))
    # Desenha alguns pixels pretos simulando uma rubrica
    for x in range(20, 180):
        img.putpixel((x, 40), (0, 0, 128, 255))
    img.save(path, format="PNG")


def test_apply_visual_signature_last_page(tmp_path: Path):
    """Testa aplicação de assinatura e carimbo de data na página 2."""
    pdf_in = tmp_path / "documento.pdf"
    sig_img = tmp_path / "assinatura.png"
    pdf_out = tmp_path / "documento_assinado.pdf"

    _create_sample_pdf(pdf_in)
    _create_signature_png(sig_img)

    result_path = apply_visual_signature(
        pdf_path=pdf_in,
        signature_img_path=sig_img,
        output_pdf_path=pdf_out,
        page_number=2,
        x_pt=100.0,
        y_pt=600.0,
        width_pt=120.0,
        height_pt=40.0,
        add_date=True,
        date_text="Assinado em 27/10/2026",
    )

    assert result_path.is_file()
    assert result_path == pdf_out

    # Validação do efeito real: abre o arquivo PDF gerado no disco
    reader = pypdf.PdfReader(result_path)
    assert len(reader.pages) == 2

    # A página 2 deve conter o texto adicionado
    p2_text = reader.pages[1].extract_text()
    assert "Assinado em 27/10/2026" in p2_text
    assert "Segunda página" in p2_text


def test_apply_visual_signature_all_pages(tmp_path: Path):
    """Testa aplicação de assinatura em todas as páginas (page_number=-1)."""
    pdf_in = tmp_path / "doc_multi.pdf"
    sig_img = tmp_path / "rubrica.png"
    pdf_out = tmp_path / "doc_rubricado.pdf"

    _create_sample_pdf(pdf_in)
    _create_signature_png(sig_img)

    apply_visual_signature(
        pdf_path=pdf_in,
        signature_img_path=sig_img,
        output_pdf_path=pdf_out,
        page_number=-1,
        x_pt=50.0,
        y_pt=50.0,
        width_pt=80.0,
        height_pt=30.0,
        add_date=True,
        date_text="Rubrica",
    )

    reader = pypdf.PdfReader(pdf_out)
    assert len(reader.pages) == 2
    assert "Rubrica" in reader.pages[0].extract_text()
    assert "Rubrica" in reader.pages[1].extract_text()
