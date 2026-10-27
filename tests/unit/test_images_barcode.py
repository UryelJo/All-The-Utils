"""
Testes de validação de efeito real para images.barcode.logic.
Gera códigos de barras e decodifica via zxing-cpp comprovando exatidão industrial.
"""
from pathlib import Path
import pytest
from PIL import Image
import zxingcpp

from wintoolbox.tools.images.barcode.logic import (
    validate_barcode_input,
    generate_barcode_image,
    generate_barcode_svg,
    save_barcode_file,
)


def test_validate_barcode_input_deterministic():
    assert validate_barcode_input("Code128", "TESTE-123") == "TESTE-123"
    assert validate_barcode_input("EAN13", "789123456789") == "789123456789"
    assert validate_barcode_input("EAN8", "1234567") == "1234567"
    assert validate_barcode_input("Standard39", "ABC-123") == "ABC-123"

    with pytest.raises(ValueError):
        validate_barcode_input("Code128", "   ")

    with pytest.raises(ValueError):
        validate_barcode_input("EAN13", "123")  # Menos de 12 dígitos

    with pytest.raises(ValueError):
        validate_barcode_input("Standard39", "abc@invalido!")


def test_generate_barcode_code128_and_read_zxing():
    # Validação do Efeito Real: Code 128
    original_text = "WIN-TOOLBOX-99"
    img = generate_barcode_image("Code128", original_text, bar_width=3, bar_height=120)

    assert isinstance(img, Image.Image)
    assert img.width > 100
    assert img.height > 100

    # Decodifica com leitor óptico real de mercado
    decoded = zxingcpp.read_barcode(img)
    assert decoded is not None
    assert decoded.text == original_text
    assert decoded.format.name == "Code128"


def test_generate_barcode_ean13_and_read_zxing():
    # Validação do Efeito Real: EAN-13
    # 789100031550 (12 dígitos) -> dígito verificador calculado automaticamente é 7
    ean_base = "789100031550"
    img = generate_barcode_image("EAN13", ean_base, bar_width=3, bar_height=120)

    decoded = zxingcpp.read_barcode(img)
    assert decoded is not None
    assert decoded.format.name == "EAN13"
    assert decoded.text.startswith(ean_base)


def test_generate_barcode_svg_structure():
    svg_str = generate_barcode_svg("Code128", "SVG-BARCODE")
    assert "<svg" in svg_str
    assert "</svg>" in svg_str
    assert "<rect" in svg_str


def test_save_barcode_file_black_box(tmp_path: Path):
    png_path = tmp_path / "code.png"
    save_barcode_file("Code128", "FILE-TEST-123", png_path, bar_width=2, bar_height=80)
    assert png_path.is_file()
    assert png_path.stat().st_size > 0

    with Image.open(png_path) as im:
        assert im.format == "PNG"

    svg_path = tmp_path / "code.svg"
    save_barcode_file("Code128", "FILE-TEST-123", svg_path)
    assert svg_path.is_file()
    assert "<svg" in svg_path.read_text(encoding="utf-8")
