"""
Testes unitários rigorosos para files.doc_metadata.logic.
Garante inspeção e higienização física real (Black-Box testing) de arquivos .docx e .pdf.
"""
from pathlib import Path
import zipfile
import pypdf
import pytest
from wintoolbox.tools.files.doc_metadata.logic import (
    clean_document,
    inspect_document,
)


def _create_mock_docx(path: Path, author: str, company: str) -> None:
    core_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        f'xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:creator>{author}</dc:creator>\n'
        f'<dc:title>Relatório Confidencial</dc:title>\n'
        f'</cp:coreProperties>'
    ).encode("utf-8")

    app_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">\n'
        f'<Company>{company}</Company>\n'
        f'</Properties>'
    ).encode("utf-8")

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", b"<w:document><w:body><w:p/></w:body></w:document>")
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)


def _create_mock_pdf(path: Path, author: str, title: str) -> None:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({
        "/Author": author,
        "/Title": title,
    })
    with open(path, "wb") as f:
        writer.write(f)


def test_docx_metadata_inspect_and_clean(tmp_path: Path):
    src_docx = tmp_path / "contrato.docx"
    _create_mock_docx(src_docx, author="Carlos Alberto", company="Corporação Global")

    info = inspect_document(str(src_docx))
    assert info["author"] == "Carlos Alberto"
    assert info["company"] == "Corporação Global"
    assert info["title"] == "Relatório Confidencial"

    # Higieniza o arquivo salvando novo arquivo
    out_docx = tmp_path / "contrato_limpo.docx"
    ok = clean_document(str(src_docx), str(out_docx))
    assert ok is True
    assert out_docx.exists()

    # Validação no arquivo limpo gerado (Black-Box)
    info_clean = inspect_document(str(out_docx))
    assert info_clean["author"] == ""
    assert info_clean["company"] == ""


def test_pdf_metadata_inspect_and_clean(tmp_path: Path):
    src_pdf = tmp_path / "artigo.pdf"
    _create_mock_pdf(src_pdf, author="Pesquisador João", title="Tese de Mestrado")

    info = inspect_document(str(src_pdf))
    assert info["author"] == "Pesquisador João"
    assert info["title"] == "Tese de Mestrado"

    # Higieniza o PDF
    out_pdf = tmp_path / "artigo_limpo.pdf"
    ok = clean_document(str(src_pdf), str(out_pdf))
    assert ok is True
    assert out_pdf.exists()

    # Validação no arquivo limpo
    info_clean = inspect_document(str(out_pdf))
    assert info_clean["author"] == ""
    assert info_clean["title"] == ""
