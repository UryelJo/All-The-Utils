"""
Testes unitários rigorosos (Black-Box Testing) para o Criador Avançado de Compactados (archive.creator_advanced).
Validação do efeito real: abertura de ZIP gerado, integridade de arquivos extraídos e divisão em volumes multipartes.
"""
from pathlib import Path
import zipfile
import pytest

from wintoolbox.tools.archive.creator_advanced.logic import (
    create_advanced_archive,
    split_file_into_volumes,
)
from wintoolbox.tools.archive.creator_advanced.tool import CreatorAdvancedTool


def test_advanced_zip_creation_and_integrity_blackbox(tmp_path: Path):
    src_dir = tmp_path / "arquivos_origem"
    src_dir.mkdir()

    # Cria arquivo com texto repetitivo para testar compressão
    f1 = src_dir / "grande_texto.txt"
    f1_content = ("WinToolbox Compactacao Avancada LZMA DEFLATE 2026\n" * 500).encode("utf-8")
    f1.write_bytes(f1_content)

    f2 = src_dir / "codigo.py"
    f2_content = b"print('Hello World All the Utils')\n"
    f2.write_bytes(f2_content)

    out_zip = tmp_path / "pacote_lzma.zip"

    # Cria com algoritmo LZMA
    res = create_advanced_archive(
        [f1, f2],
        out_zip,
        compression_method="lzma",
        compress_level=9,
    )

    assert out_zip.is_file()
    assert res["saving_percent"] > 50.0  # Texto repetitivo compacta mais de 50%
    assert res["compressed_bytes"] < res["uncompressed_bytes"]

    # DIRETRIZ ANTI-GAMBIARRA: Abre o ZIP criado e extrai para validar os dados reais
    extract_dir = tmp_path / "extraido"
    extract_dir.mkdir()

    with zipfile.ZipFile(out_zip, "r") as zf:
        zf.extractall(extract_dir)

    ext_f1 = extract_dir / "grande_texto.txt"
    ext_f2 = extract_dir / "codigo.py"

    assert ext_f1.is_file()
    assert ext_f2.is_file()
    assert ext_f1.read_bytes() == f1_content
    assert ext_f2.read_bytes() == f2_content


def test_split_file_into_volumes_and_reassembly(tmp_path: Path):
    # Cria arquivo de 2500 bytes
    dummy_file = tmp_path / "dados_grandes.bin"
    original_data = b"ABCDEFGHIJ" * 250
    dummy_file.write_bytes(original_data)

    # Divide em volumes de 1000 bytes cada (gerará 3 volumes: 1000B, 1000B, 500B)
    volumes = split_file_into_volumes(dummy_file, 1000)
    assert len(volumes) == 3
    assert volumes[0].name.endswith(".001")
    assert volumes[1].name.endswith(".002")
    assert volumes[2].name.endswith(".003")

    # Reconstrói os dados a partir dos volumes e comprova equivalência byte-a-byte
    reconstructed_data = b"".join(v.read_bytes() for v in volumes)
    assert reconstructed_data == original_data


def test_creator_advanced_invalid_method():
    with pytest.raises(ValueError, match="não suportado"):
        create_advanced_archive([], Path("teste.zip"), compression_method="INEXISTENTE")


def test_creator_advanced_tool_ui(qtbot, tmp_path: Path):
    tool = CreatorAdvancedTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria arquivo de teste
    test_f = tmp_path / "documento.txt"
    test_f.write_text("conteudo para ui de criacao")

    view._selected_items = [test_f]
    view._update_table()

    assert view._table.visible_count() == 1
    assert "1 item(ns) na fila" in view._lbl_metrics.text()

    # Simula sucesso de criação
    fake_res = {
        "output_path": str(tmp_path / "saida.zip"),
        "uncompressed_bytes": 1024,
        "compressed_bytes": 512,
        "saving_percent": 50.0,
        "elapsed_ms": 12.0,
        "volumes": [],
    }
    view._on_creation_success(fake_res)
    assert "50.0% de economia" in view._lbl_metrics.text()
