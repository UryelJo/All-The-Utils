"""
Testes de validação de efeito real para images.border_shadow.logic.
"""
from pathlib import Path
import pytest
from PIL import Image

from wintoolbox.tools.images.border_shadow.logic import (
    parse_hex_color,
    round_corners,
    apply_border_outline,
    compose_mockup,
    process_image_border_shadow,
)


def test_parse_hex_color_deterministic():
    assert parse_hex_color("#fff") == (255, 255, 255, 255)
    assert parse_hex_color("#102030") == (16, 32, 48, 255)
    assert parse_hex_color("#10203080") == (16, 32, 48, 128)
    assert parse_hex_color("invalido", alpha=100) == (255, 255, 255, 100)


def test_round_corners_real_effect():
    # Cria imagem quadrada 100x100 opaca
    base = Image.new("RGB", (100, 100), (255, 0, 0))
    rounded = round_corners(base, radius=20)

    assert rounded.mode == "RGBA"
    assert rounded.size == (100, 100)

    # O canto superior esquerdo (0,0) deve ser transparente (alpha == 0)
    corner_pixel = rounded.getpixel((0, 0))
    assert corner_pixel[3] == 0

    # O centro (50,50) deve ser totalmente opaco (alpha == 255) e vermelho
    center_pixel = rounded.getpixel((50, 50))
    assert center_pixel[0] == 255
    assert center_pixel[3] == 255


def test_compose_mockup_dimensions_and_layers():
    base = Image.new("RGBA", (200, 100), (50, 150, 250, 255))
    mockup = compose_mockup(
        image=base,
        corner_radius=10,
        border_width=2,
        shadow_blur=10,
        shadow_offset_y=8,
        shadow_opacity=0.5,
        padding=20,
        background_mode="transparent"
    )

    # Dimensões devem ser estritamente maiores que a imagem original devido ao padding e sombra
    assert mockup.width > 200
    assert mockup.height > 100
    assert mockup.mode == "RGBA"


def test_process_image_border_shadow_black_box(tmp_path: Path):
    src_file = tmp_path / "screenshot.png"
    src_img = Image.new("RGB", (300, 200), (30, 40, 50))
    src_img.save(src_file)

    out_file = tmp_path / "mockup_output.png"
    res = process_image_border_shadow(
        input_path=src_file,
        output_path=out_file,
        corner_radius=16,
        border_width=1,
        shadow_blur=20,
        shadow_offset_y=10,
        shadow_opacity=0.4,
        padding=30,
        background_mode="gradient",
        gradient_preset="slate"
    )

    assert res.is_file()
    assert res == out_file
    assert res.stat().st_size > 0

    # Abre a imagem gravada e valida efeito real
    with Image.open(res) as img:
        assert img.format == "PNG"
        assert img.size[0] > 300
        assert img.size[1] > 200

    # Teste de falha com arquivo inexistente
    with pytest.raises(FileNotFoundError):
        process_image_border_shadow(tmp_path / "nao_existe.png", tmp_path / "out.png")
