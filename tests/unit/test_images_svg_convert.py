"""
Testes de validação de efeito real para o módulo images.svg_convert.logic.
"""
from pathlib import Path
import pytest
from PIL import Image

from wintoolbox.tools.images.svg_convert.logic import (
    parse_svg_dimensions,
    convert_png_to_multi_size_ico,
    DEFAULT_ICO_SIZES,
)


def test_parse_svg_dimensions_explicit_width_height(tmp_path: Path):
    svg_file = tmp_path / "explicit.svg"
    svg_file.write_text(
        '<svg width="800px" height="600px" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>',
        encoding="utf-8"
    )
    w, h = parse_svg_dimensions(svg_file)
    assert w == 800
    assert h == 600


def test_parse_svg_dimensions_viewbox_only(tmp_path: Path):
    svg_file = tmp_path / "viewbox.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 1024 768" xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>',
        encoding="utf-8"
    )
    w, h = parse_svg_dimensions(svg_file)
    assert w == 1024
    assert h == 768


def test_parse_svg_dimensions_fallback_and_missing(tmp_path: Path):
    svg_file = tmp_path / "noviewbox.svg"
    svg_file.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
    w, h = parse_svg_dimensions(svg_file)
    assert w == 512
    assert h == 512

    with pytest.raises(FileNotFoundError):
        parse_svg_dimensions(tmp_path / "nao_existe.svg")


def test_convert_png_to_multi_size_ico_black_box(tmp_path: Path):
    # Cria um PNG real 256x256
    png_file = tmp_path / "source.png"
    img = Image.new("RGBA", (256, 256), color=(255, 100, 50, 255))
    img.save(png_file, format="PNG")

    ico_file = tmp_path / "output.ico"
    custom_sizes = [16, 32, 64]
    result_path = convert_png_to_multi_size_ico(png_file, ico_file, sizes=custom_sizes)

    assert result_path.is_file()
    assert result_path == ico_file
    assert result_path.stat().st_size > 0

    # Validação do efeito real: abre o arquivo .ico gravado e confirma que é legível pelo Pillow
    with Image.open(result_path) as ico_im:
        assert ico_im.format == "ICO"
