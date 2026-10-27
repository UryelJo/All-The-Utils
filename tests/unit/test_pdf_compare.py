"""
Testes unitários e de validação de efeito real para pdf.compare.
"""
from pathlib import Path
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.compare.logic import compare_pdf_documents


def _create_versioned_pdf(path: Path, version_text: str) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))
    # Página 1 com variação
    c.drawString(100, 750, "Documento de Especificação Técnica")
    c.drawString(100, 700, f"Versão do Sistema: {version_text}")
    c.showPage()
    # Página 2 idêntica
    c.drawString(100, 750, "Termos e Condições Gerais Inalterados")
    c.save()


def test_compare_pdfs(tmp_path: Path):
    """Testa comparação diferencial entre versões de PDF."""
    pdf_v1 = tmp_path / "doc_v1.pdf"
    pdf_v2 = tmp_path / "doc_v2.pdf"

    _create_versioned_pdf(pdf_v1, "1.0.0 Alpha")
    _create_versioned_pdf(pdf_v2, "2.0.0 Release")

    res = compare_pdf_documents(pdf_v1, pdf_v2)

    assert res["total_pages_compared"] == 2
    assert res["pages_a"] == 2
    assert res["pages_b"] == 2
    assert res["identical_pages"] == 1
    assert res["modified_pages"] == 1

    # Página 1 foi modificada
    p1 = res["pages"][0]
    assert p1["page"] == 1
    assert p1["status"] == "MODIFICADO"
    assert p1["similarity"] < 1.0
    assert any("Alpha" in l or "Release" in l for l in p1["diff_lines"])

    # Página 2 é idêntica
    p2 = res["pages"][1]
    assert p2["page"] == 2
    assert p2["status"] == "IDENTICO"
    assert p2["similarity"] == 1.0
