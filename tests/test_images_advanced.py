"""
Testes automatizados da Fase 3: Ferramentas Avançadas de Imagem.
Validação rigorosa de pixels, camadas ICO, fidelidade cromática e Black-Box testing.
"""
import json
from pathlib import Path
import pytest
from PIL import Image

import wintoolbox.tools.images
from wintoolbox.core.registry import get_tool
from wintoolbox.tools.images.resize.logic import (
    calculate_new_dimensions, resize_single_image
)
from wintoolbox.tools.images.compress.logic import compress_single_image
from wintoolbox.tools.images.watermark.logic import apply_watermark_to_image
from wintoolbox.tools.images.effects.logic import apply_image_effects_and_adjustments
from wintoolbox.tools.images.exif.logic import get_exif_info, strip_metadata
from wintoolbox.tools.images.favicon.logic import (
    generate_multi_size_ico, generate_web_favicon_package
)
from wintoolbox.tools.images.palette.logic import (
    export_palette_css, export_palette_json, extract_dominant_colors
)


def test_registry_phase_3_image_tools():
    expected_ids = [
        "images.convert",
        "images.resize",
        "images.compress",
        "images.watermark",
        "images.effects",
        "images.exif",
        "images.favicon",
        "images.palette"
    ]
    for tid in expected_ids:
        tool = get_tool(tid)
        assert tool is not None, f"Ferramenta de imagem {tid} não foi registrada."
        assert tool.name
        assert tool.category == "Imagens"


def test_calculate_new_dimensions():
    # Porcentagem
    w, h = calculate_new_dimensions(1000, 500, "Porcentagem", percent=50)
    assert w == 500 and h == 250

    # Largura Máxima
    w, h = calculate_new_dimensions(1920, 1080, "Largura Máxima (Manter Proporção)", target_w=960)
    assert w == 960 and h == 540

    # Altura Máxima
    w, h = calculate_new_dimensions(800, 600, "Altura Máxima (Manter Proporção)", target_h=300)
    assert w == 400 and h == 300

    # Caixa Exata sem manter proporção
    w, h = calculate_new_dimensions(800, 600, "Caixa Exata (Largura x Altura)", target_w=400, target_h=400, keep_aspect=False)
    assert w == 400 and h == 400


def test_resize_single_image(tmp_path: Path):
    src = tmp_path / "orig.png"
    im = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
    im.save(src)

    dst = tmp_path / "resized.png"
    ow, oh, nw, nh = resize_single_image(src, dst, {
        "mode": "Porcentagem",
        "percent": 50,
        "filter": "Lanczos (Alta Qualidade)"
    })

    assert (ow, oh) == (400, 200)
    assert (nw, nh) == (200, 100)
    assert dst.is_file()

    with Image.open(dst) as res_im:
        assert res_im.size == (200, 100)
        assert res_im.format == "PNG"


def test_compress_single_image(tmp_path: Path):
    src = tmp_path / "foto.jpg"
    im = Image.new("RGB", (600, 600), (100, 150, 200))
    im.save(src, quality=100)

    dst = tmp_path / "comprimida.jpg"
    sz_before, sz_after = compress_single_image(src, dst, {
        "mode": "Qualidade Visual Balanceada",
        "quality": 60,
        "strip_exif": True
    })

    assert dst.is_file()
    assert sz_after < sz_before
    
    # Efeito real: validar que a imagem resultante é legível e mantém resolução
    with Image.open(dst) as res_im:
        assert res_im.format == "JPEG"
        assert res_im.size == (600, 600)


def test_watermark_text_and_logo(tmp_path: Path):
    base_src = tmp_path / "base.png"
    # Fundo cinza escuro homogêneo
    base_im = Image.new("RGB", (500, 500), (30, 30, 30))
    base_im.save(base_src)

    # 1. Marca de Texto
    dst_txt = tmp_path / "com_texto.png"
    apply_watermark_to_image(base_src, dst_txt, {
        "type": "Texto",
        "text": "WinToolbox Confidencial",
        "font_size": 24,
        "opacity": 70,
        "position": "Inferior Direito",
        "margin": 20
    })
    assert dst_txt.is_file()
    with Image.open(dst_txt) as im_txt:
        assert im_txt.size == (500, 500)
        # O canto superior esquerdo (10, 10) deve continuar inalterado (30, 30, 30)
        assert im_txt.getpixel((10, 10)) == (30, 30, 30)
        # A região onde o texto foi desenhado (quadrante inferior direito) deve ter pixels diferentes da base
        modified_pixels = [
            im_txt.getpixel((x, y)) != (30, 30, 30)
            for x in range(250, 495) for y in range(420, 495)
        ]
        assert any(modified_pixels)

    # 2. Marca de Imagem (Logo amarelo no centro)
    logo_src = tmp_path / "logo.png"
    logo_im = Image.new("RGBA", (100, 100), (255, 255, 0, 255))
    logo_im.save(logo_src)

    dst_logo = tmp_path / "com_logo.png"
    apply_watermark_to_image(base_src, dst_logo, {
        "type": "Imagem (Logo)",
        "logo_path": str(logo_src),
        "logo_scale": 25,
        "opacity": 80,
        "position": "Centro"
    })
    assert dst_logo.is_file()
    with Image.open(dst_logo) as im_logo:
        # Pixel central (250, 250) deve ter sido tingido com o amarelo da logo
        center_px = im_logo.getpixel((250, 250))
        assert center_px[0] > 100 and center_px[1] > 100  # R e G elevados (amarelo)


def test_image_effects_and_adjustments(tmp_path: Path):
    src = tmp_path / "colorida.png"
    im = Image.new("RGB", (200, 200), (180, 70, 50))
    im.save(src)

    # Filtro Sépia
    dst_sepia = tmp_path / "sepia.png"
    apply_image_effects_and_adjustments(src, dst_sepia, {
        "effect": "Sépia Vintage",
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "sharpness": 1.0
    })
    assert dst_sepia.is_file()
    with Image.open(dst_sepia) as im_sepia:
        r, g, b = im_sepia.getpixel((100, 100))
        # Tom sépia clássico: R > G > B
        assert r > g > b

    # Filtro Preto e Branco (Tons de cinza: R == G == B em todos os pixels)
    dst_pb = tmp_path / "pb.png"
    apply_image_effects_and_adjustments(src, dst_pb, {
        "effect": "Preto e Branco (Tons de Cinza)",
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "sharpness": 1.0
    })
    assert dst_pb.is_file()
    with Image.open(dst_pb) as im_pb:
        r, g, b = im_pb.getpixel((100, 100))
        assert r == g == b


def test_strip_metadata(tmp_path: Path):
    src = tmp_path / "foto_exif.jpg"
    im = Image.new("RGB", (300, 300), (80, 120, 160))
    im.save(src)

    dst = tmp_path / "foto_limpa.jpg"
    strip_metadata(src, dst, remove_gps_only=False)
    assert dst.is_file()

    info = get_exif_info(dst)
    assert info.get("gps_lat") is None
    assert info.get("gps_lon") is None


def test_favicon_generation(tmp_path: Path):
    src = tmp_path / "logo_app.png"
    im = Image.new("RGBA", (256, 256), (0, 120, 212, 255))
    im.save(src)

    # 1. Arquivo .ico multi-resolução
    ico_dst = tmp_path / "app.ico"
    generate_multi_size_ico(src, ico_dst, [16, 32, 64])
    assert ico_dst.is_file()
    
    # Valida cabeçalho do arquivo ICO (formato binário: primeiros 6 bytes = 0, 1, count)
    ico_bytes = ico_dst.read_bytes()
    assert ico_bytes[:4] == b"\x00\x00\x01\x00"  # ICO format
    num_images = int.from_bytes(ico_bytes[4:6], "little")
    assert num_images == 3  # 16, 32, 64

    # 2. Pacote Web Favicon
    pack_dir = tmp_path / "web_pack"
    res = generate_web_favicon_package(src, pack_dir, app_name="Teste App", theme_color="#FF5500")

    assert (pack_dir / "favicon.ico").is_file()
    assert (pack_dir / "apple-touch-icon.png").is_file()
    assert (pack_dir / "site.webmanifest").is_file()
    assert "<link rel=\"apple-touch-icon\"" in res["html_snippet"]

    with Image.open(pack_dir / "apple-touch-icon.png") as apple_im:
        assert apple_im.size == (180, 180)


def test_dominant_colors_palette(tmp_path: Path):
    src = tmp_path / "quadro_cores.png"
    im = Image.new("RGB", (100, 100), (255, 0, 0))  # Vermelho
    im.paste((0, 255, 0), (0, 0, 50, 100))          # Metade Verde
    im.save(src)

    colors = extract_dominant_colors(src, num_colors=2)
    assert len(colors) == 2
    hexes = [c["hex"].upper() for c in colors]
    assert any(h == "#FF0000" for h in hexes)
    assert any(h == "#00FF00" for h in hexes)

    # Exportações
    css = export_palette_css(colors)
    assert ":root {" in css
    assert "--color-1:" in css
    assert "--color-2:" in css

    js_str = export_palette_json(colors)
    data = json.loads(js_str)
    assert "palette" in data
    assert len(data["palette"]) == 2
