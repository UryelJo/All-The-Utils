"""
Testes unitários e de integração para archive.iso_tools.
"""
import json
from pathlib import Path
import subprocess
import pytest

from wintoolbox.tools.archive.iso_tools.logic import (
    mount_disk_image,
    dismount_disk_image,
    list_mounted_disk_images,
    extract_iso_contents,
)


def test_mount_invalid_file(tmp_path: Path):
    """Testa rejeição de arquivo de imagem inexistente."""
    fake_path = tmp_path / "nao_existe.iso"
    with pytest.raises(FileNotFoundError):
        mount_disk_image(fake_path)


def test_mount_invalid_extension(tmp_path: Path):
    """Testa rejeição de extensão inválida."""
    txt_path = tmp_path / "arquivo.txt"
    txt_path.write_text("dummy")
    with pytest.raises(ValueError, match="Extensão de imagem não suportada"):
        mount_disk_image(txt_path)


def test_mount_disk_image_powershell_mock(tmp_path: Path, monkeypatch):
    """Testa montagem de imagem virtual com mock de resposta PowerShell."""
    iso_path = tmp_path / "teste.iso"
    iso_path.write_bytes(b"\x00" * 2048)

    mock_json = json.dumps({
        "DriveLetter": "G",
        "FileSystemLabel": "ISO_TESTE",
        "Size": 104857600,
    })

    def mock_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = mock_json
            stderr = ""
        return MockResult()

    monkeypatch.setattr(subprocess, "run", mock_run)

    res = mount_disk_image(iso_path, read_only=True)
    assert res["status"] == "MONTADO"
    assert res["drive_letter"] == "G:"
    assert res["label"] == "ISO_TESTE"
    assert res["size"] == 104857600
    assert res["read_only"] is True


def test_dismount_disk_image_powershell_mock(tmp_path: Path, monkeypatch):
    """Testa desmontagem de imagem virtual."""
    iso_path = tmp_path / "teste.iso"
    iso_path.write_bytes(b"\x00" * 2048)

    def mock_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = ""
            stderr = ""
        return MockResult()

    monkeypatch.setattr(subprocess, "run", mock_run)

    res = dismount_disk_image(iso_path)
    assert res["status"] == "DESMONTADO"
    assert res["image_path"] == str(iso_path.resolve())


def test_list_mounted_disk_images_mock(monkeypatch):
    """Testa listagem de imagens montadas ativas."""
    mock_json = json.dumps([
        {
            "ImagePath": r"C:\ISOs\ubuntu.iso",
            "Attached": True,
            "StorageType": 1,
            "DriveLetter": "F",
        }
    ])

    def mock_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = mock_json
            stderr = ""
        return MockResult()

    monkeypatch.setattr(subprocess, "run", mock_run)

    items = list_mounted_disk_images()
    assert len(items) == 1
    assert items[0]["image_path"] == r"C:\ISOs\ubuntu.iso"
    assert items[0]["drive_letter"] == "F:"
    assert items[0]["attached"] is True
