"""
Testes unitários rigorosos (Black-Box Testing) para o Gerador de PDF Pesquisável com OCR (pdf.ocr_searchable).
Validação do efeito real: extração de texto via pypdf.PdfReader do arquivo PDF gerado fisicamente.
"""
from pathlib import Path
from PIL import Image
import pypdf
import pytest

from wintoolbox.tools.pdf.ocr_searchable.logic import (
    convert_scanned_pdf_to_searchable,
    create_searchable_page_pdf,
)
from wintoolbox.tools.pdf.ocr_searchable.tool import OcrSearchablePdfTool


def test_searchable_pdf_real_generation_and_text_extraction_blackbox(tmp_path: Path):
    # Cria uma imagem real simulando uma página digitalizada
    scan_image = tmp_path / "pagina_digitalizada.png"
    img = Image.new("RGB", (600, 800), color=(240, 240, 240))
    img.save(scan_image)

    out_pdf = tmp_path / "documento_pesquisavel.pdf"

    # Simula motor OCR determinístico
    texto_esperado = "CONTRATO DE PRESTACAO DE SERVICOS WINTOOLBOX 2026"
    mock_ocr = lambda pil_img: texto_esperado

    res = convert_scanned_pdf_to_searchable(
        scan_image,
        out_pdf,
        ocr_fn=mock_ocr,
    )

    assert out_pdf.is_file()
    assert res["total_pages"] == 1
    assert res["total_words"] > 0

    # DIRETRIZ ANTI-GAMBIARRA: Abre o PDF real resultante com pypdf.PdfReader e extrai o texto da camada de OCR
    reader = pypdf.PdfReader(str(out_pdf))
    assert len(reader.pages) == 1
    extracted_text = reader.pages[0].extract_text()

    assert texto_esperado in extracted_text


def test_searchable_pdf_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        convert_scanned_pdf_to_searchable(tmp_path / "nao_existe.png", tmp_path / "saida.pdf")


def test_ocr_searchable_tool_ui(qtbot, tmp_path: Path):
    tool = OcrSearchablePdfTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria imagem de teste
    test_img = tmp_path / "teste_scan.png"
    Image.new("RGB", (200, 200), color="white").save(test_img)

    view._selected_input_file = test_img
    view._txt_input_path.setText(str(test_img))

    # Simula resposta de sucesso
    fake_res = {
        "output_path": str(tmp_path / "pesquisavel.pdf"),
        "total_pages": 2,
        "total_words": 150,
        "extracted_text": "Texto extraído com sucesso da página 1 e 2.",
    }
    view._on_conversion_success(fake_res)

    assert "Texto extraído com sucesso" in view._txt_preview.toPlainText()
    assert "2 página(s)" in view._lbl_status.text()
