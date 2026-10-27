"""
Testes unitários rigorosos para files.robocopy_gui.logic.
Validação determinística da montagem de comandos do Robocopy e interpretação de códigos de saída.
"""
import pytest
from wintoolbox.tools.files.robocopy_gui.logic import (
    build_robocopy_command,
    parse_robocopy_exit_code,
    parse_robocopy_summary,
)


def test_build_robocopy_command_mirror():
    cmd = build_robocopy_command(
        source_dir="C:\\Origem",
        target_dir="D:\\Backup",
        mode="mirror",
        threads=8,
        restartable=True,
        dry_run=True,
        exclude_dirs=[".git", "node_modules"],
        exclude_files=["*.tmp"],
    )

    assert cmd[0] == "robocopy"
    assert "C:\\Origem" in cmd
    assert "D:\\Backup" in cmd
    assert "/MIR" in cmd
    assert "/MT:8" in cmd
    assert "/Z" in cmd
    assert "/L" in cmd
    assert "/XD" in cmd
    assert ".git" in cmd
    assert "/XF" in cmd
    assert "*.tmp" in cmd


def test_build_robocopy_command_newer_only():
    cmd = build_robocopy_command(
        source_dir="C:\\Dados",
        target_dir="E:\\Destino",
        mode="newer_only",
        threads=1,
        restartable=False,
        dry_run=False,
    )

    assert "/E" in cmd
    assert "/XO" in cmd
    assert "/MIR" not in cmd
    assert "/L" not in cmd
    assert "/Z" not in cmd


def test_parse_robocopy_exit_codes():
    # 0 = Nenhuma alteração
    res0 = parse_robocopy_exit_code(0)
    assert res0["is_success"] is True
    assert res0["is_error"] is False
    assert "Nenhum arquivo copiado" in res0["details"][0]

    # 1 = Arquivos copiados com sucesso
    res1 = parse_robocopy_exit_code(1)
    assert res1["is_success"] is True
    assert "Um ou mais arquivos copiados" in res1["details"][0]

    # 3 = 1 + 2 (Arquivos copiados + arquivos extras)
    res3 = parse_robocopy_exit_code(3)
    assert res3["is_success"] is True
    assert len(res3["details"]) == 2

    # 8 = Falha/erro
    res8 = parse_robocopy_exit_code(8)
    assert res8["is_error"] is True
    assert res8["is_success"] is False
    assert "ERRO" in res8["details"][0]


def test_parse_robocopy_summary():
    mock_output = """
    ------------------------------------------------------------------------------
                   Total    Copiado    Ignorado Incompatível     ERRO    Extras
        Pastas :      12          4           8            0        0         0
      Arquivos :     140         25         115            0        0         0
         Bytes :   4.2 m      1.1 m       3.1 m            0        0         0
    ------------------------------------------------------------------------------
    """
    stats = parse_robocopy_summary(mock_output)
    assert stats["dirs_total"] == 12
    assert stats["dirs_copied"] == 4
    assert stats["files_total"] == 140
    assert stats["files_copied"] == 25
