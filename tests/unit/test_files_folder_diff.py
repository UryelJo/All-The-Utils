"""
Testes unitários rigorosos (Black-Box Testing) para o Comparador de Pastas (files.folder_diff).
Validação determinística de estruturas de diretórios reais, hashes e classificação.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.files.folder_diff.logic import (
    compare_directories,
    scan_directory_tree,
)
from wintoolbox.tools.files.folder_diff.tool import FolderDiffTool


def test_folder_diff_full_blackbox(tmp_path: Path):
    dir_a = tmp_path / "pasta_a"
    dir_b = tmp_path / "pasta_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # 1. Arquivo Idêntico em ambas
    sub_a = dir_a / "sub"
    sub_b = dir_b / "sub"
    sub_a.mkdir()
    sub_b.mkdir()
    (sub_a / "comum.txt").write_bytes(b"conteudo 100% identico")
    (sub_b / "comum.txt").write_bytes(b"conteudo 100% identico")

    # 2. Arquivo Modificado (mesmo caminho relativo, conteúdo diferente)
    (dir_a / "config.ini").write_bytes(b"versao=1.0\n")
    (dir_b / "config.ini").write_bytes(b"versao=2.0\n")

    # 3. Arquivo Apenas em A
    (dir_a / "apenas_em_a.log").write_bytes(b"registro a")

    # 4. Arquivo Apenas em B
    (dir_b / "apenas_em_b.pdf").write_bytes(b"%PDF fake")

    # Executa a comparação com hash profundo ativo
    result = compare_directories(dir_a, dir_b, deep_hash_compare=True)
    summary = result["summary"]
    records = result["records"]

    assert summary["total_files"] == 4
    assert summary["identical"] == 1
    assert summary["modified"] == 1
    assert summary["only_a"] == 1
    assert summary["only_b"] == 1

    # Verifica os registros individuais
    r_map = {r["rel_path"]: r["status"] for r in records}
    assert r_map["sub/comum.txt"] == "IDENTICO"
    assert r_map["config.ini"] == "MODIFICADO"
    assert r_map["apenas_em_a.log"] == "APENAS_EM_A"
    assert r_map["apenas_em_b.pdf"] == "APENAS_EM_B"


def test_folder_diff_ignore_patterns(tmp_path: Path):
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "arquivo.txt").write_text("ok")
    (dir_b / "arquivo.txt").write_text("ok")

    # Arquivos que devem ser ignorados por padrão
    (dir_a / "temp.tmp").write_text("lixo")
    (dir_b / "temp.tmp").write_text("lixo")

    result = compare_directories(dir_a, dir_b, ignore_patterns=["*.tmp"])
    assert result["summary"]["total_files"] == 1
    assert result["summary"]["identical"] == 1


def test_folder_diff_nonexistent_directory_error(tmp_path: Path):
    with pytest.raises(NotADirectoryError):
        scan_directory_tree(tmp_path / "pasta_fantasma")


def test_folder_diff_tool_ui(qtbot, tmp_path: Path):
    tool = FolderDiffTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria diretórios reais
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "teste.txt").write_text("conteudo a")
    (dir_b / "teste.txt").write_text("conteudo b")

    view._txt_dir_a.setText(str(dir_a))
    view._txt_dir_b.setText(str(dir_b))

    res = compare_directories(dir_a, dir_b, deep_hash_compare=False)
    view._on_diff_success(res)

    assert view._table.visible_count() == 1
    assert "Modificados: 0" in view._lbl_summary.text() or "Idênticos: 1" in view._lbl_summary.text()
