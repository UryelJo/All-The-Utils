"""
Testes unitários da lógica de conversão de imagens.
"""
from pathlib import Path
from PIL import Image
from wintoolbox.tools.images.convert.logic import convert_single_image

def test_convert_png_to_webp(tmp_path: Path):
    src = tmp_path / "teste.png"
    # Cria uma imagem RGBA com canal alfa
    im = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    im.save(src, format="PNG")

    dst = tmp_path / "teste.webp"
    convert_single_image(src, dst, target_format="WEBP", quality=85)

    assert dst.exists()
    with Image.open(dst) as out_img:
        assert out_img.format == "WEBP"
        assert out_img.size == (100, 100)

def test_convert_rgba_to_jpeg(tmp_path: Path):
    # JPEG não suporta canal alfa; nossa lógica deve mesclar com fundo branco sem falhar
    src = tmp_path / "transparente.png"
    im = Image.new("RGBA", (60, 60), (0, 255, 0, 100))
    im.save(src, format="PNG")

    dst = tmp_path / "saida.jpg"
    convert_single_image(src, dst, target_format="JPG", quality=90)

    assert dst.exists()
    with Image.open(dst) as out_img:
        assert out_img.format == "JPEG"
        assert out_img.mode == "RGB"
