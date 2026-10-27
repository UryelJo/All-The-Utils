"""
Testes unitários rigorosos para files.cleanup_finder.logic.
Garante detecção precisa e higienização física real (Black-Box testing) com asserções determinísticas.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.files.cleanup_finder.logic import (
    execute_cleanup,
    scan_cleanup_candidates,
)


def test_scan_and_cleanup_candidates(tmp_path: Path):
    root = tmp_path / "area_teste"
    root.mkdir()

    # 1. Arquivo normal (deve ser preservado)
    f_ok = root / "arquivo_util.txt"
    f_ok.write_text("conteúdo legítimo e importante", encoding="utf-8")

    # 2. Arquivo de 0 byte (deve ser detectado)
    f_zero = root / "temp_zero_byte.log"
    f_zero.write_bytes(b"")

    # 3. Pasta vazia (deve ser detectada)
    dir_empty = root / "pasta_vazia"
    dir_empty.mkdir()

    # 4. Pasta com arquivo dentro (não deve ser marcada como vazia)
    dir_with_file = root / "pasta_cheia"
    dir_with_file.mkdir()
    (dir_with_file / "foto.png").write_bytes(b"PNG_DATA_123")

    # Simulação (Dry Run)
    candidates = scan_cleanup_candidates(
        str(root),
        find_empty_dirs=True,
        find_zero_byte_files=True,
        find_broken_shortcuts=True,
    )

    types_found = {c["type"] for c in candidates}
    paths_found = {c["path"] for c in candidates}

    assert "Arquivo 0 Byte" in types_found
    assert "Pasta Vazia" in types_found
    assert str(f_zero) in paths_found
    assert str(dir_empty) in paths_found
    assert str(f_ok) not in paths_found
    assert str(dir_with_file) not in paths_found

    # Executa a limpeza física direta
    res = execute_cleanup(candidates, use_trash=False)
    assert res["success_count"] == 2
    assert res["failed_count"] == 0

    # Validação física no disco após a limpeza (Black-Box)
    assert not f_zero.exists()
    assert not dir_empty.exists()
    assert f_ok.exists()
    assert f_ok.read_text(encoding="utf-8") == "conteúdo legítimo e importante"
    assert (dir_with_file / "foto.png").exists()


def test_scan_nonexistent_directory():
    with pytest.raises(FileNotFoundError, match="não encontrado"):
        scan_cleanup_candidates("C:/caminho/inexistente/para/limpeza_123")
