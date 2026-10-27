"""
Testes unitários rigorosos para files.type_detector.logic.
Garante identificação precisa de Magic Bytes, detecção de divergências e correção de extensão.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.files.type_detector.logic import (
    correct_file_extension,
    detect_file_type,
)


def test_detect_png_matched(tmp_path: Path):
    f_png = tmp_path / "imagem_valida.png"
    f_png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20)

    res = detect_file_type(str(f_png))
    assert res["is_mismatch"] is False
    assert res["real_type"] == "PNG Image"
    assert res["recommended_ext"] == ".png"
    assert res["mime_type"] == "image/png"


def test_detect_masked_executable(tmp_path: Path):
    # Executável Windows (MZ) mascarado com extensão de imagem .jpg
    f_fake_jpg = tmp_path / "perfil_usuario.jpg"
    f_fake_jpg.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 30)

    res = detect_file_type(str(f_fake_jpg))
    assert res["is_mismatch"] is True
    assert res["real_type"] == "Windows Executable (PE / MZ)"
    assert res["recommended_ext"] == ".exe"
    assert res["declared_ext"] == ".jpg"


def test_detect_pdf_masked_as_txt(tmp_path: Path):
    f_fake_txt = tmp_path / "documento.txt"
    f_fake_txt.write_bytes(b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n")

    res = detect_file_type(str(f_fake_txt))
    assert res["is_mismatch"] is True
    assert res["real_type"] == "PDF Document"
    assert res["recommended_ext"] == ".pdf"


def test_detect_docx_uses_zip_compatible(tmp_path: Path):
    # Arquivos Office (.docx) usam cabeçalho ZIP PK\x03\x04
    f_docx = tmp_path / "trabalho.docx"
    f_docx.write_bytes(b"PK\x03\x04\x14\x00\x06\x00" + b"\x00" * 20)

    res = detect_file_type(str(f_docx))
    assert res["is_mismatch"] is False
    assert "ZIP" in res["real_type"]


def test_correct_file_extension(tmp_path: Path):
    f_bad = tmp_path / "musica.txt"
    f_bad.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x20" + b"\x00" * 50)

    info = detect_file_type(str(f_bad))
    assert info["is_mismatch"] is True
    assert info["recommended_ext"] == ".mp3"

    out_dir = tmp_path / "fixed"
    fixed_path = correct_file_extension(str(f_bad), info["recommended_ext"], str(out_dir))

    assert Path(fixed_path).exists()
    assert Path(fixed_path).name == "musica.mp3"
    assert Path(fixed_path).read_bytes() == f_bad.read_bytes()


def test_detect_empty_file(tmp_path: Path):
    f_empty = tmp_path / "vazio.bin"
    f_empty.write_bytes(b"")

    res = detect_file_type(str(f_empty))
    assert res["file_size"] == 0
    assert "0 byte" in res["real_type"]
    assert res["is_mismatch"] is False
