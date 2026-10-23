"""
Testes automatizados para a Fase 8: Ferramentas Adicionais de Imagem e Desktop.
Valida o registro e as lógicas puras das 7 ferramentas.
"""
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

from wintoolbox.core.registry import get_all_tools, get_tool
from wintoolbox.tools.images.gif_tools.logic import (
    create_animated_gif, extract_gif_frames
)
from wintoolbox.tools.images.collage.logic import create_image_collage
from wintoolbox.tools.images.color_picker.logic import rgb_to_formats
from wintoolbox.tools.images.qrcode.logic import generate_qrcode
from wintoolbox.tools.images.screenshot.logic import (
    apply_annotations_to_image, save_screenshot
)
from wintoolbox.tools.images.ocr.logic import perform_ocr_on_image
from wintoolbox.tools.images.remove_bg.logic import remove_image_background


@pytest.fixture
def sample_test_images(tmp_path: Path) -> list[Path]:
    """Gera 3 imagens coloridas para testes de colagem e GIF."""
    images = []
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for i, col in enumerate(colors):
        p = tmp_path / f"sample_{i}.png"
        img = Image.new("RGB", (100, 100), col)
        img.save(p)
        images.append(p)
    return images


def test_phase_8_tools_registered():
    """Valida se todas as 7 ferramentas da Fase 8 estão devidamente registradas."""
    expected_ids = [
        "images.gif_tools",
        "images.collage",
        "images.color_picker",
        "images.qrcode",
        "images.screenshot",
        "images.ocr",
        "images.remove_bg",
    ]
    all_tools = {t.id: t for t in get_all_tools()}
    for t_id in expected_ids:
        assert t_id in all_tools, f"Ferramenta {t_id} não registrada."
        tool = get_tool(t_id)
        assert tool.category == "Imagens"
        assert len(tool.description) > 0


def test_gif_create_and_extract(sample_test_images: list[Path], tmp_path: Path):
    """Valida compilação de GIF animado e extração de quadros."""
    gif_out = tmp_path / "resultado.gif"
    res = create_animated_gif(sample_test_images, gif_out, frame_duration_ms=100)
    assert res.is_file()
    assert res.stat().st_size > 0

    extract_dir = tmp_path / "extracted_frames"
    frames = extract_gif_frames(res, extract_dir, output_format="PNG")
    assert len(frames) == len(sample_test_images)
    for f in frames:
        assert f.is_file()


def test_image_collage(sample_test_images: list[Path], tmp_path: Path):
    """Valida geração de colagem em grade."""
    collage_out = tmp_path / "colagem.png"
    res = create_image_collage(
        sample_test_images,
        collage_out,
        cols=2,
        spacing=10,
        bg_color=(255, 255, 255),
        cell_size=(100, 100)
    )
    assert res.is_file()

    with Image.open(res) as img:
        assert img.width > 200
        assert img.height > 200


def test_color_picker_formats():
    """Valida conversão precisa para HEX, RGB, HSL e CMYK."""
    formats = rgb_to_formats(255, 0, 0)
    assert formats["hex"] == "#FF0000"
    assert formats["rgb"] == "rgb(255, 0, 0)"
    assert "hsl(0, 100%, 50%)" in formats["hsl"]
    assert "cmyk" in formats

    white = rgb_to_formats(255, 255, 255)
    assert white["hex"] == "#FFFFFF"


def test_qrcode_generator(tmp_path: Path):
    """Valida geração de imagem de QR Code."""
    qr_out = tmp_path / "meu_qr.png"
    img = generate_qrcode("https://github.com", output_path=qr_out)
    assert qr_out.is_file()
    assert img.width >= 50
    assert img.height >= 50


def test_screenshot_annotations(tmp_path: Path):
    """Valida anotações sobre captura de tela."""
    base = Image.new("RGB", (300, 200), (200, 200, 200))
    rects = [(10, 10, 100, 100, "#FF0000", 3)]
    texts = [(20, 20, "Texto Teste", "#0000FF", 16)]

    annotated = apply_annotations_to_image(base, rectangles=rects, texts=texts)
    out_p = tmp_path / "anotado.png"
    saved = save_screenshot(annotated, out_p)
    assert saved.is_file()


def test_ocr_logic(tmp_path: Path):
    """Valida execução de OCR em imagem com texto legível."""
    ocr_img_p = tmp_path / "ocr_sample.png"
    img = Image.new("RGB", (400, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 30), "TESTE OCR 123", fill=(0, 0, 0))
    img.save(ocr_img_p)

    text_found = perform_ocr_on_image(ocr_img_p)
    assert isinstance(text_found, str)
    assert len(text_found) > 0


def test_remove_bg_logic(tmp_path: Path):
    """Valida remoção de fundo com canal alpha transparente."""
    src_p = tmp_path / "fundo_verde.png"
    img = Image.new("RGB", (100, 100), (0, 255, 0))
    # Desenha um círculo vermelho no centro
    draw = ImageDraw.Draw(img)
    draw.ellipse([30, 30, 70, 70], fill=(255, 0, 0))
    img.save(src_p)

    out_p = tmp_path / "sem_fundo.png"
    res = remove_image_background(
        src_p,
        out_p,
        mode="custom",
        custom_color=(0, 255, 0),
        tolerance=30
    )
    assert res.is_file()

    with Image.open(res) as result_img:
        assert result_img.mode == "RGBA"
        # O canto (0, 0) que era verde deve estar transparente (alpha = 0)
        alpha_corner = result_img.getpixel((0, 0))[3]
        assert alpha_corner == 0
        # O centro (50, 50) que era vermelho deve estar opaco (alpha = 255)
        alpha_center = result_img.getpixel((50, 50))[3]
        assert alpha_center > 200
