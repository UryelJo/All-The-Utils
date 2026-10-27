"""
Testes de validação de efeito real para system.fonts_manager.logic.
"""
from pathlib import Path
import sys
import pytest

from wintoolbox.tools.system.fonts_manager.logic import (
    FontInfo,
    get_user_fonts_dir,
    get_system_fonts_dir,
    extract_font_metadata,
    install_font_for_current_user,
)


def test_fonts_directories_paths():
    user_dir = get_user_fonts_dir()
    assert isinstance(user_dir, Path)
    assert "Fonts" in str(user_dir)

    sys_dir = get_system_fonts_dir()
    assert isinstance(sys_dir, Path)
    assert "Fonts" in str(sys_dir)


@pytest.mark.skipif(sys.platform != "win32", reason="Requer Windows com fontes de sistema padrão")
def test_extract_font_metadata_real_font():
    sys_dir = get_system_fonts_dir()
    arial_path = sys_dir / "arial.ttf"

    if arial_path.is_file():
        meta = extract_font_metadata(arial_path)
        assert meta.family == "Arial"
        assert meta.format_type == "TrueType"
        assert meta.file_name.lower() == "arial.ttf"
        assert meta.is_user_font is False


def test_extract_font_metadata_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        extract_font_metadata(tmp_path / "nao_existe.ttf")


def test_install_font_unsupported_extension(tmp_path: Path):
    dummy = tmp_path / "teste.txt"
    dummy.write_text("conteudo", encoding="utf-8")

    ok, msg = install_font_for_current_user(dummy)
    assert ok is False
    assert "Formato não suportado" in msg
