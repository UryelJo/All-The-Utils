"""
Testes unitários rigorosos para a lógica de images.text_extractor.

Valida a sanitização de texto, manipulação de regiões de imagem e
integração com os motores de OCR.
"""
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from wintoolbox.tools.images.text_extractor.logic import (
    clean_extracted_text,
    extract_text_from_image_region,
)


def test_clean_extracted_text():
    """Valida a limpeza determinística de textos com quebras de linha irregulares."""
    raw = "   Linha 1 com espaços   \n\n\n   Linha 2   \n\n   Linha 3   \n"
    cleaned = clean_extracted_text(raw)
    assert cleaned == "Linha 1 com espaços\nLinha 2\nLinha 3"

    assert clean_extracted_text("") == ""
    assert clean_extracted_text("   \n\n   ") == ""


def test_extract_text_from_image_region_mocked_ocr(tmp_path: Path):
    """Valida o recorte e chamada ao motor de OCR."""
    img = Image.new("RGB", (300, 200), (255, 255, 255))

    with patch("wintoolbox.tools.images.text_extractor.logic.perform_ocr_on_image", return_value="Texto Reconhecido"):
        res = extract_text_from_image_region(img, crop_box=(10, 10, 100, 50), temp_dir=tmp_path)
        assert res == "Texto Reconhecido"


def test_extract_text_from_image_region_invalid_box():
    """Casos de borda: coordenadas com largura zero ou invertidas."""
    img = Image.new("RGB", (100, 100))
    res = extract_text_from_image_region(img, crop_box=(50, 50, 50, 50))
    assert res == ""
