"""
Testes de validação de efeito real para system.wsl_manager.logic.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.system.wsl_manager.logic import (
    WslDistro,
    decode_wsl_output,
    parse_wsl_list_output,
    parse_wslconfig,
    write_wslconfig,
)


def test_decode_wsl_output_utf16_and_utf8():
    text_sample = "  NAME   STATE   VERSION\n* Ubuntu Running 2"
    # Simula saída UTF-16LE com bytes nulos típica do wsl.exe no Windows
    utf16_bytes = text_sample.encode("utf-16le")
    decoded_16 = decode_wsl_output(utf16_bytes)
    assert "Ubuntu" in decoded_16
    assert "Running" in decoded_16

    utf8_bytes = text_sample.encode("utf-8")
    decoded_8 = decode_wsl_output(utf8_bytes)
    assert "Ubuntu" in decoded_8


def test_parse_wsl_list_output_deterministic():
    sample_table = """
  NAME                   STATE           VERSION
* Ubuntu-22.04           Running         2
  docker-desktop         Stopped         2
  Debian                 Running         1
    """
    distros = parse_wsl_list_output(sample_table)
    assert len(distros) == 3

    u = distros[0]
    assert u.name == "Ubuntu-22.04"
    assert u.state == "Running"
    assert u.version == 2
    assert u.is_default is True

    d = distros[1]
    assert d.name == "docker-desktop"
    assert d.state == "Stopped"
    assert d.version == 2
    assert d.is_default is False

    deb = distros[2]
    assert deb.name == "Debian"
    assert deb.version == 1


def test_wslconfig_black_box_read_write(tmp_path: Path):
    cfg_file = tmp_path / ".wslconfig"

    # Gravação do arquivo .wslconfig real
    res_path = write_wslconfig(
        memory="6GB",
        processors=4,
        swap="1GB",
        path=cfg_file
    )
    assert res_path.is_file()
    assert res_path == cfg_file

    # Validação do Efeito Real: lê o arquivo INI gerado
    parsed = parse_wslconfig(cfg_file)
    assert parsed["memory"] == "6GB"
    assert parsed["processors"] == "4"
    assert parsed["swap"] == "1GB"

    # Atualização parcial
    write_wslconfig(memory="12GB", path=cfg_file)
    updated = parse_wslconfig(cfg_file)
    assert updated["memory"] == "12GB"
    assert updated["processors"] == "4"
