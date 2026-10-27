"""
Testes unitários rigorosos (Black-Box Testing) para o Extrator em Lote (archive.multi_extract).
Validação do efeito real: abertura e leitura exata de arquivos descompactados e proteção contra Zip Slip.
"""
from pathlib import Path
import zipfile
import pytest

from wintoolbox.tools.archive.multi_extract.logic import (
    extract_batch_archives,
    extract_single_archive,
    is_safe_path,
)
from wintoolbox.tools.archive.multi_extract.tool import MultiExtractTool


def test_batch_extract_blackbox_real_files(tmp_path: Path):
    src_dir = tmp_path / "origem"
    out_dir = tmp_path / "destino"
    src_dir.mkdir()
    out_dir.mkdir()

    # Cria pacote 1
    zip1 = src_dir / "relatorios.zip"
    with zipfile.ZipFile(zip1, "w") as zf:
        zf.writestr("vendas.txt", "Vendas totais: R$ 50.000,00")
        zf.writestr("dados/resumo.csv", "id,valor\n1,100\n")

    # Cria pacote 2
    zip2 = src_dir / "fotos.zip"
    with zipfile.ZipFile(zip2, "w") as zf:
        zf.writestr("foto1.bin", b"\x00\x01\x02\x03dados_foto")

    # Executa a extração em lote com subpastas ativadas
    results = extract_batch_archives([zip1, zip2], out_dir, create_subfolder=True)
    assert len(results) == 2
    assert results[0]["status"] == "OK"
    assert results[1]["status"] == "OK"

    # DIRETRIZ ANTI-GAMBIARRA: Abre e lê os arquivos reais descompactados no disco
    vendas_real = out_dir / "relatorios" / "vendas.txt"
    assert vendas_real.is_file()
    assert vendas_real.read_text(encoding="utf-8") == "Vendas totais: R$ 50.000,00"

    resumo_real = out_dir / "relatorios" / "dados" / "resumo.csv"
    assert resumo_real.is_file()
    assert resumo_real.read_text(encoding="utf-8") == "id,valor\n1,100\n"

    foto_real = out_dir / "fotos" / "foto1.bin"
    assert foto_real.is_file()
    assert foto_real.read_bytes() == b"\x00\x01\x02\x03dados_foto"


def test_zip_slip_security_blocking(tmp_path: Path):
    out_dir = tmp_path / "destino_seguro"
    out_dir.mkdir()

    # Cria arquivo ZIP com tentativa de path traversal malicioso
    malicious_zip = tmp_path / "exploit.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        # Tenta escapar do diretório de extração
        zf.writestr("../../arquivo_vazado.txt", "dados maliciosos")

    with pytest.raises(ValueError, match="Zip Slip detectado"):
        extract_single_archive(malicious_zip, out_dir, create_subfolder=False)

    # O arquivo malicioso NUNCA deve ter sido criado fora da pasta
    assert not (tmp_path.parent / "arquivo_vazado.txt").exists()


def test_is_safe_path_boundaries(tmp_path: Path):
    base = tmp_path / "base"
    base.mkdir()

    assert is_safe_path(base, "arquivo.txt") is True
    assert is_safe_path(base, "pasta/subpasta/arquivo.txt") is True
    assert is_safe_path(base, "../escapou.txt") is False
    assert is_safe_path(base, "../../windows/win.ini") is False


def test_multi_extract_tool_ui(qtbot, tmp_path: Path):
    tool = MultiExtractTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria arquivo zip para o teste
    test_zip = tmp_path / "teste.zip"
    with zipfile.ZipFile(test_zip, "w") as zf:
        zf.writestr("item.txt", "ola mundo")

    view._selected_archives = [test_zip]
    view._txt_output_dir.setText(str(tmp_path / "saida_ui"))

    res = extract_batch_archives([test_zip], tmp_path / "saida_ui", create_subfolder=True)
    view._on_extract_success(res)

    assert view._table.visible_count() == 1
    assert "1 com sucesso" in view._lbl_status.text()
