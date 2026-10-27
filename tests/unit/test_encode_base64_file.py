"""
Testes unitários rigorosos (Black-Box com validação de bytes reais) para encode.base64_file.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.encode.base64_file.logic import (
    base64_to_file,
    detect_mime_type,
    file_to_base64,
    parse_data_uri,
)
from wintoolbox.tools.encode.base64_file.tool import Base64FileTool


def test_base64_file_roundtrip_blackbox(tmp_path: Path):
    # Cria arquivo real simulando imagem PNG com magic bytes oficiais
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    original_file = tmp_path / "sample.png"
    original_file.write_bytes(png_bytes)

    # 1. Converte para Base64 com Data URI
    encoded_info = file_to_base64(original_file, include_data_uri=True)
    assert encoded_info["file_size"] == len(png_bytes)
    assert encoded_info["mime_type"] == "image/png"
    assert encoded_info["data_uri"].startswith("data:image/png;base64,")

    # 2. Converte de volta para arquivo físico
    restored_file = tmp_path / "restored.png"
    result = base64_to_file(encoded_info["data_uri"], restored_file)

    assert result["file_size"] == len(png_bytes)
    assert result["mime_type"] == "image/png"
    assert restored_file.is_file()

    # Validação do Efeito Real: os bytes no disco devem ser idênticos
    assert restored_file.read_bytes() == png_bytes


def test_base64_raw_string_without_data_uri(tmp_path: Path):
    arbitrary_bytes = b"WinToolbox 2026 - Dados binarios puros \x00\x01\x02\xff"
    src_file = tmp_path / "data.bin"
    src_file.write_bytes(arbitrary_bytes)

    encoded_info = file_to_base64(src_file, include_data_uri=False)
    assert encoded_info["data_uri"] == ""
    assert len(encoded_info["base64_str"]) > 0

    dest_file = tmp_path / "data_out.bin"
    base64_to_file(encoded_info["base64_str"], dest_file)
    assert dest_file.read_bytes() == arbitrary_bytes


def test_base64_file_edge_cases_and_errors(tmp_path: Path):
    # Arquivo inexistente
    with pytest.raises(FileNotFoundError):
        file_to_base64(tmp_path / "nao_existe.txt")

    # Entrada vazia
    with pytest.raises(ValueError, match="vazia"):
        parse_data_uri("   ")

    # Data URI malformado sem separador
    with pytest.raises(ValueError, match="Data URI malformado"):
        parse_data_uri("data:image/png;base64")

    # Base64 corrompido
    with pytest.raises(ValueError, match="inválidos ou corrompidos"):
        parse_data_uri("data:image/png;base64,###CARACTERES_INVALIDOS_B64###")


def test_base64_file_tool_ui(qtbot, tmp_path: Path):
    tool = Base64FileTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria arquivo temporário de teste
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"Ola mundo Base64")

    # Simula seleção de arquivo
    view._selected_input_file = test_file
    view._txt_file_path.setText(str(test_file))
    view._convert_selected_file()

    output_txt = view._txt_b64_output.toPlainText()
    assert output_txt.startswith("data:text/plain;base64,")

    # Simula aba de decodificação
    view._txt_b64_input.setPlainText(output_txt)
    output_restored = tmp_path / "restaurado_ui.txt"
    res = base64_to_file(output_txt, output_restored)
    assert output_restored.read_bytes() == b"Ola mundo Base64"
    assert res["file_size"] == 16
