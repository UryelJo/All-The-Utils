"""
Testes unitários e de validação de efeito real para pdf.metadata_bookmarks.
"""
from pathlib import Path
import pypdf
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.metadata_bookmarks.logic import (
    extract_metadata_and_bookmarks,
    save_metadata_and_bookmarks,
)


def _create_3page_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(595.27, 841.89))
    for i in range(1, 4):
        c.drawString(100, 750, f"Página {i}")
        c.showPage()
    c.save()


def test_save_and_extract_metadata_and_bookmarks(tmp_path: Path):
    """Testa gravação e leitura de metadados e bookmarks em PDF."""
    pdf_in = tmp_path / "original.pdf"
    pdf_out = tmp_path / "atualizado.pdf"

    _create_3page_pdf(pdf_in)

    meta_input = {
        "title": "Manual do Desenvolvedor",
        "author": "Equipe de Engenharia",
        "subject": "Documentação Oficial",
        "keywords": "python, pdf, ferramentas",
    }

    bookmarks_input = [
        {"title": "Introdução", "page": 1},
        {"title": "Configuração", "page": 2},
        {"title": "Conclusão", "page": 3},
    ]

    res_path = save_metadata_and_bookmarks(
        pdf_path=pdf_in,
        output_pdf_path=pdf_out,
        metadata=meta_input,
        bookmarks=bookmarks_input,
    )

    assert res_path.is_file()

    # Validação do efeito real: abre o arquivo gerado com PdfReader
    reader = pypdf.PdfReader(res_path)
    meta = reader.metadata
    assert meta.get("/Title") == "Manual do Desenvolvedor"
    assert meta.get("/Author") == "Equipe de Engenharia"

    # Extrai via lógica e confere bookmarks
    extracted = extract_metadata_and_bookmarks(res_path)
    assert extracted["metadata"]["title"] == "Manual do Desenvolvedor"
    assert len(extracted["bookmarks"]) == 3
    assert extracted["bookmarks"][0]["title"] == "Introdução"
    assert extracted["bookmarks"][0]["page"] == 1
    assert extracted["bookmarks"][2]["title"] == "Conclusão"
    assert extracted["bookmarks"][2]["page"] == 3
