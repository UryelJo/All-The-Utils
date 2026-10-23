"""
Lógica pura de filtros e ajustes de imagem (Brilho, Contraste, Saturação, Sépia, P&B, Desfoque).
"""
from pathlib import Path
from typing import Any, Dict
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

IMAGE_EFFECTS = [
    "Nenhum",
    "Preto e Branco (Tons de Cinza)",
    "Sépia Vintage",
    "Inversão de Cores (Negativo)",
    "Desfoque Gaussiano",
    "Auto-Contraste Dinâmico",
    "Detecção de Bordas (Contorno)",
    "Realce de Detalhes"
]

def apply_sepia(im: Image.Image) -> Image.Image:
    """Aplica o filtro sépia fotográfico clássico."""
    im_rgb = im.convert("RGB")
    width, height = im_rgb.size
    pixels = im_rgb.load()

    for py in range(height):
        for px in range(width):
            r, g, b = pixels[px, py]
            tr = int(0.393 * r + 0.769 * g + 0.189 * b)
            tg = int(0.349 * r + 0.686 * g + 0.168 * b)
            tb = int(0.272 * r + 0.534 * g + 0.131 * b)
            pixels[px, py] = (min(255, tr), min(255, tg), min(255, tb))
    return im_rgb

def apply_image_effects_and_adjustments(src: Path, dst: Path, params: Dict[str, Any]) -> None:
    """Aplica os filtros e ajustes configurados na imagem e grava no destino."""
    brightness = params.get("brightness", 1.0)
    contrast = params.get("contrast", 1.0)
    saturation = params.get("saturation", 1.0)
    sharpness = params.get("sharpness", 1.0)
    effect = params.get("effect", "Nenhum")
    blur_radius = params.get("blur_radius", 2.0)

    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        # Se a imagem tiver alfa e for salvar em JPEG depois, manteremos referência
        has_alpha = im.mode in ("RGBA", "LA")
        working_im = im.copy()

        # 1. Efeitos Artísticos
        if effect == "Preto e Branco (Tons de Cinza)":
            working_im = ImageOps.grayscale(working_im).convert("RGB")
        elif effect == "Sépia Vintage":
            working_im = apply_sepia(working_im)
        elif effect == "Inversão de Cores (Negativo)":
            if working_im.mode in ("RGBA", "LA"):
                # Inverte apenas os canais RGB preservando alfa
                r, g, b, a = working_im.convert("RGBA").split()
                rgb_inv = ImageOps.invert(Image.merge("RGB", (r, g, b)))
                r2, g2, b2 = rgb_inv.split()
                working_im = Image.merge("RGBA", (r2, g2, b2, a))
            else:
                working_im = ImageOps.invert(working_im.convert("RGB"))
        elif effect == "Desfoque Gaussiano":
            working_im = working_im.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        elif effect == "Auto-Contraste Dinâmico":
            if working_im.mode != "RGB":
                working_im = ImageOps.autocontrast(working_im.convert("RGB"))
            else:
                working_im = ImageOps.autocontrast(working_im)
        elif effect == "Detecção de Bordas (Contorno)":
            working_im = working_im.filter(ImageFilter.FIND_EDGES)
        elif effect == "Realce de Detalhes":
            working_im = working_im.filter(ImageFilter.DETAIL)

        # 2. Ajustes Numéricos (ImageEnhance)
        if brightness != 1.0:
            working_im = ImageEnhance.Brightness(working_im).enhance(brightness)
        if contrast != 1.0:
            working_im = ImageEnhance.Contrast(working_im).enhance(contrast)
        if saturation != 1.0 and working_im.mode in ("RGB", "RGBA"):
            working_im = ImageEnhance.Color(working_im).enhance(saturation)
        if sharpness != 1.0:
            working_im = ImageEnhance.Sharpness(working_im).enhance(sharpness)

        # 3. Salvar
        ext = dst.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            if working_im.mode in ("RGBA", "LA", "P"):
                rgb_im = Image.new("RGB", working_im.size, (255, 255, 255))
                if working_im.mode == "RGBA":
                    rgb_im.paste(working_im, mask=working_im.split()[3])
                else:
                    rgb_im.paste(working_im.convert("RGB"))
                rgb_im.save(dst, format="JPEG", quality=92, optimize=True)
            else:
                working_im.save(dst, format="JPEG", quality=92, optimize=True)
        elif ext == ".png":
            working_im.save(dst, format="PNG", optimize=True)
        elif ext == ".webp":
            working_im.save(dst, format="WEBP", quality=90)
        else:
            working_im.save(dst)
