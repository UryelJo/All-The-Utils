"""
Testes unitários e de validação de efeito real para pdf.redact.
"""
from pathlib import Path
import pypdf
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.redact.logic import redact_terms_and_regions


def _create_confidential_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))
    c.drawString(100, 750, "Documento de Recursos Humanos")
    c.drawString(100, 700, "Funcionario: Joao da Silva")
    c.drawString(100, 680, "CPF: 123.456.789-00")
    c.drawString(100, 660, "Salario Confidencial: R$ 99.000,00")
    c.save()


def test_redact_terms(tmp_path: Path):
    """Testa tarjamento de palavras-chave confidenciais em PDF."""
    pdf_in = tmp_path / "confidencial.pdf"
    pdf_out = tmp_path / "censurado.pdf"

    _create_confidential_pdf(pdf_in)

    res = redact_terms_and_regions(
        pdf_path=pdf_in,
        output_pdf_path=pdf_out,
        terms=["123.456.789-00", "99.000,00"],
        case_sensitive=False,
        fill_color_black=True,
    )

    assert res["status"] == "CONCLUIDO"
    assert res["total_redactions"] >= 2
    assert pdf_out.is_file()

    # Validação física do PDF gerado
    reader = pypdf.PdfReader(pdf_out)
    assert len(reader.pages) == 1
