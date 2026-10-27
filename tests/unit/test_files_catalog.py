"""
Testes unitários rigorosos para files.catalog.logic.
Validação em disco de snapshots reais de catálogos (Black-Box testing) com asserções determinísticas.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.files.catalog.logic import (
    format_bytes,
    load_catalog_from_file,
    save_catalog_to_file,
    scan_directory_catalog,
    search_catalog_entries,
)


def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(10 * 1024 * 1024) == "10.0 MB"
    assert format_bytes(2 * 1024 * 1024 * 1024) == "2.00 GB"


def test_scan_save_and_search_catalog(tmp_path: Path):
    # Cria estrutura de teste
    root = tmp_path / "meu_drive"
    sub1 = root / "Documentos"
    sub2 = root / "Videos" / "2026"
    sub1.mkdir(parents=True)
    sub2.mkdir(parents=True)

    (sub1 / "relatorio_anual.pdf").write_bytes(b"PDF_DUMMY_DATA_123")
    (sub1 / "planilha_gastos.xlsx").write_bytes(b"EXCEL_DUMMY_DATA_456789")
    (sub2 / "apresentacao.mp4").write_bytes(b"MP4_VIDEO_DUMMY_DATA_BYTES")

    # Escaneia
    cat = scan_directory_catalog(str(root), catalog_name="DriveDeTestes")
    assert cat["catalog_name"] == "DriveDeTestes"
    assert cat["total_files"] == 3
    assert cat["total_dirs"] >= 3
    assert cat["total_bytes"] > 0
    assert len(cat["entries"]) == 3

    # Salva em arquivo
    cat_file = tmp_path / "snapshot.json"
    save_catalog_to_file(cat, str(cat_file))
    assert cat_file.exists()

    # Recarrega em disco (Black-Box)
    loaded_cat = load_catalog_from_file(str(cat_file))
    assert loaded_cat["catalog_name"] == "DriveDeTestes"
    assert loaded_cat["total_files"] == 3

    # Busca por texto no nome
    res_relatorio = search_catalog_entries(loaded_cat, query="relatorio")
    assert len(res_relatorio) == 1
    assert res_relatorio[0]["name"] == "relatorio_anual.pdf"
    assert res_relatorio[0]["ext"] == ".pdf"

    # Busca por extensão
    res_mp4 = search_catalog_entries(loaded_cat, extension="mp4")
    assert len(res_mp4) == 1
    assert res_mp4[0]["name"] == "apresentacao.mp4"

    # Busca sem resultados
    res_none = search_catalog_entries(loaded_cat, query="arquivo_inexistente")
    assert res_none == []


def test_scan_nonexistent_directory():
    with pytest.raises(FileNotFoundError, match="não encontrado"):
        scan_directory_catalog("C:/caminho/completamente/invalido/para/teste_xyz")
