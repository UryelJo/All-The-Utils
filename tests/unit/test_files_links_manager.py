"""
Testes unitários rigorosos para files.links_manager.logic.
Garante inspeção de ponteiros, detecção de links quebrados e remoção segura sem afetar alvos.
"""
import os
from pathlib import Path
import pytest
from wintoolbox.tools.files.links_manager.logic import (
    inspect_pointer,
    remove_link_safely,
    scan_ntfs_links,
)


def test_inspect_and_remove_hardlink(tmp_path: Path):
    target = tmp_path / "original.txt"
    target.write_text("dados_originais", encoding="utf-8")

    link = tmp_path / "copia_hardlink.txt"
    try:
        os.link(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("Hardlinks não suportados no sistema de arquivos atual.")

    info = inspect_pointer(str(link))
    assert info is not None
    assert info["type"] == "Hardlink"
    assert info["nlink"] >= 2

    # Remoção segura do hardlink
    ok = remove_link_safely(str(link))
    assert ok is True
    assert not link.exists()
    assert target.exists()  # Alvo original permanece intacto
    assert target.read_text(encoding="utf-8") == "dados_originais"


def test_inspect_symlink_and_broken_detection(tmp_path: Path):
    target_dir = tmp_path / "alvo_pasta"
    target_dir.mkdir()
    (target_dir / "arquivo.txt").write_text("conteúdo", encoding="utf-8")

    symlink_dir = tmp_path / "atalho_para_pasta"
    try:
        os.symlink(target_dir, symlink_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks requerem privilégios de desenvolvedor no Windows.")

    info = inspect_pointer(str(symlink_dir))
    assert info is not None
    assert info["is_broken"] is False
    assert "Ativo" in info["status"]

    # Quebra o alvo apagando target_dir
    os.rmdir(target_dir / "arquivo.txt") if (target_dir / "arquivo.txt").is_dir() else (target_dir / "arquivo.txt").unlink()
    os.rmdir(target_dir)

    broken_info = inspect_pointer(str(symlink_dir))
    assert broken_info is not None
    assert broken_info["is_broken"] is True
    assert "Quebrado" in broken_info["status"]

    # Remove o link quebrado
    assert remove_link_safely(str(symlink_dir)) is True
    assert not os.path.islink(str(symlink_dir))


def test_scan_ntfs_links(tmp_path: Path):
    root = tmp_path / "busca"
    root.mkdir()
    f1 = root / "arq1.txt"
    f1.write_text("teste", encoding="utf-8")
    f2 = root / "arq2_hl.txt"

    try:
        os.link(f1, f2)
    except (OSError, NotImplementedError):
        pytest.skip("Hardlinks não suportados.")

    found = scan_ntfs_links(str(root))
    assert len(found) >= 1
    names = {item["name"] for item in found}
    assert "arq2_hl.txt" in names or "arq1.txt" in names
