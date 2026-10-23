"""
Testes automatizados da Fase 3: Ferramentas Avançadas de Imagem.
Valida registro, redimensionamento, compressão, marcas d'água, efeitos, EXIF, favicons e paleta.
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
    """Valida se todas as 8 ferramentas da categoria de Imagens estão registradas."""
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
    """Valida as regras de cálculo dimensional proporcional e exato."""
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
    """Testa o redimensionamento real de imagem em disco."""
    src = tmp_path / "orig.png"
    im = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
    im.save(src)

    dst = tmp_path / "resized.png"
    ow, oh, nw, nh = resize_single_image(src, dst, {
        "mode": "Porcentagem",
        "percent": 50,
        "filter": "Lanczos (Alta Qualidade)"
    })

    assert ow == 400 and oh == 200
    assert nw == 200 and nh == 100
    assert dst.exists()

    with Image.open(dst) as res_im:
        assert res_im.size == (200, 100)


def test_compress_single_image(tmp_path: Path):
    """Testa a compressão de imagem PNG e JPEG."""
    src = tmp_path / "foto.jpg"
    im = Image.new("RGB", (600, 600), (100, 150, 200))
    im.save(src, quality=100)

    dst = tmp_path / "comprimida.jpg"
    sz_before, sz_after = compress_single_image(src, dst, {
        "mode": "Qualidade Visual Balanceada",
        "quality": 60,
        "strip_exif": True
    })

    assert dst.exists()
    assert sz_after > 0


def test_watermark_text_and_logo(tmp_path: Path):
    """Testa a aplicação de marca d'água de texto e de logo."""
    base_src = tmp_path / "base.png"
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
    assert dst_txt.exists()

    # 2. Marca de Imagem (Logo)
    logo_src = tmp_path / "logo.png"
    logo_im = Image.new("RGBA", (100, 100), (255, 255, 0, 180))
    logo_im.save(logo_src)

    dst_logo = tmp_path / "com_logo.png"
    apply_watermark_to_image(base_src, dst_logo, {
        "type": "Imagem (Logo)",
        "logo_path": str(logo_src),
        "logo_scale": 25,
        "opacity": 60,
        "position": "Centro"
    })
    assert dst_logo.exists()


def test_image_effects_and_adjustments(tmp_path: Path):
    """Testa aplicação de sépia, desfoque e ajustes de brilho."""
    src = tmp_path / "colorida.png"
    im = Image.new("RGB", (200, 200), (180, 70, 50))
    im.save(src)

    # Filtro Sépia com ajuste de contraste
    dst_sepia = tmp_path / "sepia.png"
    apply_image_effects_and_adjustments(src, dst_sepia, {
        "effect": "Sépia Vintage",
        "brightness": 1.1,
        "contrast": 1.2,
        "saturation": 1.0,
        "sharpness": 1.0
    })
    assert dst_sepia.exists()

    # Filtro Preto e Branco
    dst_pb = tmp_path / "pb.png"
    apply_image_effects_and_adjustments(src, dst_pb, {
        "effect": "Preto e Branco (Tons de Cinza)",
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "sharpness": 1.0
    })
    assert dst_pb.exists()


def test_strip_metadata(tmp_path: Path):
    """Testa a limpeza de metadados de fotos."""
    src = tmp_path / "foto_exif.jpg"
    im = Image.new("RGB", (300, 300), (80, 120, 160))
    im.save(src)

    dst = tmp_path / "foto_limpa.jpg"
    strip_metadata(src, dst, remove_gps_only=False)
    assert dst.exists()

    info = get_exif_info(dst)
    assert not info["gps_lat"]


def test_favicon_generation(tmp_path: Path):
    """Testa a geração de arquivo .ico e do pacote completo web."""
    src = tmp_path / "logo_app.png"
    im = Image.new("RGBA", (256, 256), (0, 120, 212, 255))
    im.save(src)

    # 1. Arquivo .ico multi-resolução
    ico_dst = tmp_path / "app.ico"
    generate_multi_size_ico(src, ico_dst, [16, 32, 64])
    assert ico_dst.exists()
    assert ico_dst.stat().st_size > 0

    # 2. Pacote Web Favicon
    pack_dir = tmp_path / "web_pack"
    res = generate_web_favicon_package(src, pack_dir, app_name="Teste App", theme_color="#FF5500")

    assert (pack_dir / "favicon.ico").exists()
    assert (pack_dir / "apple-touch-icon.png").exists()
    assert (pack_dir / "site.webmanifest").exists()
    assert "<link rel=\"apple-touch-icon\"" in res["html_snippet"]


def test_dominant_colors_palette(tmp_path: Path):
    """Testa a extração de paleta de cores dominante e exportação CSS/JSON."""
    src = tmp_path / "quadro_cores.png"
    im = Image.new("RGB", (100, 100), (255, 0, 0))  # Vermelho
    im.paste((0, 255, 0), (0, 0, 50, 100))          # Metade Verde
    im.save(src)

    colors = extract_dominant_colors(src, num_colors=2)
    assert len(colors) >= 2
    hexes = [c["hex"].upper() for c in colors]
    assert any(h.startswith("#FF") or h.startswith("#00") for h in hexes)

    # Exportações
    css = export_palette_css(colors)
    assert ":root {" in css
    assert "--color-1:" in css

    js_str = export_palette_json(colors)
    data = json.loads(js_str)
    assert "palette" in data
    assert len(data["palette"]) >= 2
