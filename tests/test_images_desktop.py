"""
Testes automatizados para a Fase 8: Ferramentas Adicionais de Imagem e Desktop.
Validação rigorosa de decodificação de QR Code, dimensões exatas de colagem,
pixels de anotação e remoção de fundo com canal alfa.
"""
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
import zxingcpp

from wintoolbox.core.registry import get_all_tools, get_tool
from wintoolbox.tools.images.gif_tools.logic import (
    create_animated_gif, extract_gif_frames
)
from wintoolbox.tools.images.collage.logic import create_image_collage
from wintoolbox.tools.images.color_picker.logic import rgb_to_formats
from wintoolbox.tools.images.qrcode.logic import generate_qrcode, decode_qrcode_from_image
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
    gif_out = tmp_path / "resultado.gif"
    res = create_animated_gif(sample_test_images, gif_out, frame_duration_ms=100)
    assert res.is_file()

    # Validação do GIF compilado: formato e contagem de quadros
    with Image.open(res) as gif_im:
        assert gif_im.format == "GIF"
        assert getattr(gif_im, "n_frames", 1) == 3

    extract_dir = tmp_path / "extracted_frames"
    frames = extract_gif_frames(res, extract_dir, output_format="PNG")
    assert len(frames) == 3
    for f in frames:
        assert f.is_file()
        with Image.open(f) as frame_im:
            assert frame_im.format == "PNG"
            assert frame_im.size == (100, 100)


def test_image_collage(sample_test_images: list[Path], tmp_path: Path):
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

    # Cálculo determinístico: 3 imagens em 2 colunas -> 2 linhas e 2 colunas
    # width = (2 * 100) + (3 * 10) = 230
    # height = (2 * 100) + (3 * 10) = 230
    with Image.open(res) as img:
        assert img.size == (230, 230)
        assert img.format == "PNG"


def test_color_picker_formats():
    formats = rgb_to_formats(255, 0, 0)
    assert formats["hex"] == "#FF0000"
    assert formats["rgb"] == "rgb(255, 0, 0)"
    assert formats["hsl"] == "hsl(0, 100%, 50%)"
    assert formats["cmyk"] == "cmyk(0%, 100%, 100%, 0%)"

    white = rgb_to_formats(255, 255, 255)
    assert white["hex"] == "#FFFFFF"
    assert white["rgb"] == "rgb(255, 255, 255)"


def test_qrcode_generator_and_real_decoding(tmp_path: Path):
    """Gera QR code e decodifica com zxingcpp para comprovar o payload exato."""
    qr_out = tmp_path / "meu_qr.png"
    expected_url = "https://github.com/UryelJo/WinToolbox"
    generate_qrcode(expected_url, output_path=qr_out)
    assert qr_out.is_file()

    # Validação do Efeito Real: decodificar via leitor de código de barras
    decoded_text = decode_qrcode_from_image(qr_out)
    assert decoded_text == expected_url


def test_screenshot_annotations(tmp_path: Path):
    # Fundo cinza uniforme (200, 200, 200)
    base = Image.new("RGB", (300, 200), (200, 200, 200))
    rects = [(10, 10, 100, 100, "#FF0000", 3)]
    texts = [(20, 20, "Texto Teste", "#0000FF", 16)]

    annotated = apply_annotations_to_image(base, rectangles=rects, texts=texts)
    out_p = tmp_path / "anotado.png"
    saved = save_screenshot(annotated, out_p)
    assert saved.is_file()

    with Image.open(saved) as im:
        assert im.size == (300, 200)
        # O pixel da borda do retângulo (10, 10) deve ter sido pintado de vermelho (255, 0, 0)
        assert im.getpixel((10, 10)) == (255, 0, 0)
        # Um pixel fora da anotação deve permanecer cinza original (200, 200, 200)
        assert im.getpixel((5, 5)) == (200, 200, 200)


def test_ocr_logic(tmp_path: Path):
    ocr_img_p = tmp_path / "ocr_sample.png"
    img = Image.new("RGB", (400, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 30), "TESTE OCR 123", fill=(0, 0, 0))
    img.save(ocr_img_p)

    text_found = perform_ocr_on_image(ocr_img_p)
    assert isinstance(text_found, str)
    # Deve conter fragmentos reconhecíveis do texto inserido
    assert any(term in text_found.upper() for term in ("TESTE", "OCR", "123"))


def test_remove_bg_logic(tmp_path: Path):
    src_p = tmp_path / "fundo_verde.png"
    img = Image.new("RGB", (100, 100), (0, 255, 0))
    # Desenha um círculo vermelho sólido no centro
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
        # O canto (0, 0) que era verde deve estar totalmente transparente (alpha = 0)
        alpha_corner = result_img.getpixel((0, 0))[3]
        assert alpha_corner == 0

        # O centro (50, 50) que era vermelho deve estar totalmente opaco (alpha = 255)
        pixel_center = result_img.getpixel((50, 50))
        assert pixel_center[0] == 255  # Vermelho
        assert pixel_center[3] == 255  # Opaco
