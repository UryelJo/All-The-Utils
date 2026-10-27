"""
Testes unitários rigorosos (Black-Box Testing) para o Editor de Metadados PDF (pdf.metadata_editor).
Validação do efeito real: abertura de PDFs físicos gerados com pypdf e verificação exata de propriedades e limpeza.
"""
from pathlib import Path
import pypdf
import pytest

from wintoolbox.tools.pdf.metadata_editor.logic import (
    batch_sanitize_metadata,
    read_pdf_metadata,
    update_pdf_metadata,
)
from wintoolbox.tools.pdf.metadata_editor.tool import PdfMetadataEditorTool


def _create_sample_pdf(file_path: Path, author: str = "Autor Antigo", title: str = "Titulo Antigo"):
    """Cria um PDF real físico com metadados para os testes blackbox."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.add_metadata({
        "/Author": author,
        "/Title": title,
        "/Subject": "Assunto Teste",
        "/Keywords": "segurança, pdf",
        "/Creator": "Software Antigo",
    })
    with open(file_path, "wb") as f:
        writer.write(f)


def test_pdf_metadata_update_blackbox(tmp_path: Path):
    src_pdf = tmp_path / "origem.pdf"
    _create_sample_pdf(src_pdf, author="Autor Antigo", title="Titulo Antigo")

    out_pdf = tmp_path / "atualizado.pdf"

    # Atualiza metadados
    update_pdf_metadata(
        src_pdf,
        out_pdf,
        new_metadata={"author": "Engenheiro WinToolbox", "title": "Relatório Oficial 2026"},
        clean_all=False,
    )

    assert out_pdf.is_file()

    # DIRETRIZ ANTI-GAMBIARRA: Abre o PDF físico resultante com pypdf.PdfReader e valida
    reader = pypdf.PdfReader(str(out_pdf))
    assert reader.metadata.author == "Engenheiro WinToolbox"
    assert reader.metadata.title == "Relatório Oficial 2026"
    assert reader.metadata.subject == "Assunto Teste"  # Preservado


def test_pdf_metadata_sanitize_privacy_blackbox(tmp_path: Path):
    src_pdf = tmp_path / "com_rastros.pdf"
    _create_sample_pdf(src_pdf, author="Funcionario Confidencial", title="Documento Estratégico")

    out_clean_pdf = tmp_path / "anonimizado.pdf"

    # Higienização de privacidade completa
    update_pdf_metadata(src_pdf, out_clean_pdf, clean_all=True)

    assert out_clean_pdf.is_file()

    # DIRETRIZ ANTI-GAMBIARRA: Abre o PDF físico gerado e comprova que os metadados foram apagados
    reader = pypdf.PdfReader(str(out_clean_pdf))
    meta = reader.metadata
    assert not meta.author or meta.author == ""
    assert not meta.title or meta.title == ""
    assert not meta.creator or meta.creator == ""


def test_batch_sanitize_metadata(tmp_path: Path):
    src1 = tmp_path / "doc1.pdf"
    src2 = tmp_path / "doc2.pdf"
    _create_sample_pdf(src1, author="User 1")
    _create_sample_pdf(src2, author="User 2")

    out_dir = tmp_path / "higienizados"

    results = batch_sanitize_metadata([src1, src2], out_dir)
    assert len(results) == 2
    assert results[0]["status"] == "OK"
    assert results[1]["status"] == "OK"

    # Valida arquivo do lote
    limpo1 = Path(results[0]["output_path"])
    reader = pypdf.PdfReader(str(limpo1))
    assert not reader.metadata.author


def test_pdf_metadata_editor_tool_ui(qtbot, tmp_path: Path):
    tool = PdfMetadataEditorTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria PDF e simula carregamento
    test_pdf = tmp_path / "teste_ui.pdf"
    _create_sample_pdf(test_pdf, author="Admin UI", title="Documento UI")

    view._current_pdf_path = test_pdf
    view._txt_single_path.setText(str(test_pdf))

    meta = read_pdf_metadata(test_pdf)
    for k, field in view._fields.items():
        field.setText(meta.get(k, ""))

    assert view._fields["author"].text() == "Admin UI"
    assert view._fields["title"].text() == "Documento UI"
