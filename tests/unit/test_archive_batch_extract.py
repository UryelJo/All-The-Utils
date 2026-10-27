"""
Testes unitários e de integração para archive.batch_extract.
Validação de efeito real no disco com arquivos ZIP reais e testes de segurança.
"""
from pathlib import Path
import zipfile
import pytest

from wintoolbox.tools.archive.batch_extract.logic import (
    extract_archive_item,
    is_safe_relative_path,
    detect_single_root_folder_zip,
)


def test_batch_extract_zip_normal(tmp_path: Path):
    """Testa extração de ZIP comum com arquivos e subpastas."""
    zip_path = tmp_path / "meu_pacote.zip"
    out_dir = tmp_path / "extraidos"
    out_dir.mkdir()

    # Cria ZIP com 2 arquivos reais
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("arquivo1.txt", "Conteúdo número 1")
        zf.writestr("subpasta/arquivo2.txt", "Conteúdo número 2")

    res = extract_archive_item(
        archive_path=zip_path,
        output_dir=out_dir,
        create_subfolder=True,
        avoid_duplicate_root=True,
        delete_source_after=False,
    )

    dest_folder = Path(res["dest_folder"])
    assert dest_folder == out_dir / "meu_pacote"
    assert (dest_folder / "arquivo1.txt").is_file()
    assert (dest_folder / "subpasta" / "arquivo2.txt").is_file()

    # Validação física de bytes exatos
    assert (dest_folder / "arquivo1.txt").read_text(encoding="utf-8") == "Conteúdo número 1"
    assert (dest_folder / "subpasta" / "arquivo2.txt").read_text(encoding="utf-8") == "Conteúdo número 2"
    assert res["files_count"] == 2
    assert zip_path.is_file()  # Não foi excluído


def test_batch_extract_delete_source_after(tmp_path: Path):
    """Testa exclusão do arquivo fonte após extração bem-sucedida."""
    zip_path = tmp_path / "temporario.zip"
    out_dir = tmp_path / "saida"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("teste.bin", b"\x01\x02\x03\x04")

    res = extract_archive_item(
        archive_path=zip_path,
        output_dir=out_dir,
        create_subfolder=True,
        delete_source_after=True,
    )

    assert not zip_path.exists()
    dest_file = Path(res["dest_folder"]) / "teste.bin"
    assert dest_file.is_file()
    assert dest_file.read_bytes() == b"\x01\x02\x03\x04"


def test_batch_extract_avoid_duplicate_root(tmp_path: Path):
    """Testa remoção inteligente de pasta raiz duplicada."""
    zip_path = tmp_path / "projeto.zip"
    out_dir = tmp_path / "saida_dup"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("projeto/main.py", "print('hello')")
        zf.writestr("projeto/config.json", "{}")

    # Com avoid_duplicate_root=True, o destino deve ser saida_dup/projeto/main.py (e NÃO saida_dup/projeto/projeto/main.py)
    res = extract_archive_item(
        archive_path=zip_path,
        output_dir=out_dir,
        create_subfolder=True,
        avoid_duplicate_root=True,
    )

    dest_folder = Path(res["dest_folder"])
    assert (dest_folder / "main.py").is_file()
    assert not (dest_folder / "projeto" / "main.py").exists()
    assert (dest_folder / "main.py").read_text(encoding="utf-8") == "print('hello')"


def test_batch_extract_zip_slip_security(tmp_path: Path):
    """Testa bloqueio de ataque Zip Slip (path traversal malicioso)."""
    zip_path = tmp_path / "malicioso.zip"
    out_dir = tmp_path / "alvo"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../ataque.txt", "conteúdo malicioso")

    with pytest.raises(ValueError, match="Ataque Path Traversal"):
        extract_archive_item(
            archive_path=zip_path,
            output_dir=out_dir,
            create_subfolder=True,
        )
