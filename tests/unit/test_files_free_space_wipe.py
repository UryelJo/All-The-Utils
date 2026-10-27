"""
Testes unitários rigorosos para files.free_space_wipe.logic.
Garante cálculo de espaço em disco, montagem de comando cipher /w e sobrescrita segura temporária.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.files.free_space_wipe.logic import (
    build_cipher_wipe_command,
    get_drive_space_info,
    sanitize_free_space_python,
)


def test_build_cipher_wipe_command(tmp_path: Path):
    cmd = build_cipher_wipe_command(str(tmp_path))
    assert cmd[0] == "cipher"
    assert len(cmd) == 2
    assert cmd[1].startswith("/w:")
    assert str(tmp_path.resolve()) in cmd[1]


def test_get_drive_space_info(tmp_path: Path):
    info = get_drive_space_info(str(tmp_path))
    assert info["total_bytes"] > 0
    assert info["free_bytes"] > 0
    assert "GB" in info["total_formatted"] or "MB" in info["total_formatted"]
    assert 0 <= info["percent_free"] <= 100


def test_sanitize_free_space_python_with_limit(tmp_path: Path):
    test_dir = tmp_path / "wipe_target"
    test_dir.mkdir()

    res = sanitize_free_space_python(str(test_dir), max_mb=2, pattern=b"\xAA")

    assert res["success"] is True
    assert res["bytes_wiped"] == 2 * 1024 * 1024
    assert res["mb_wiped"] == 2.0

    # Garante que o arquivo temporário foi expurgado e não sobrou resquício no disco
    temp_files = list(test_dir.glob("_wipe_temp_*"))
    assert temp_files == []


def test_get_space_nonexistent_directory():
    with pytest.raises(FileNotFoundError, match="não encontrado"):
        get_drive_space_info("C:/caminho/invalido/para/disco_xyz")
