"""
Lógica pura para aplicação de cantos arredondados, sombras, molduras e fundos decorativos.

Permite transformar capturas de tela e recortes em mockups elegantes
com sombra difusa realista, cantos suaves e fundos com gradiente ou transparência.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter
from wintoolbox.tools.images.convert.logic import ensure_heif_registered

ensure_heif_registered()


def parse_hex_color(hex_str: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Converte string hex (#RGB, #RRGGBB, #RRGGBBAA) para tupla RGBA."""
    s = hex_str.strip().lstrip("#")
    try:
        if len(s) == 3:
            r, g, b = [int(c * 2, 16) for c in s]
            return (r, g, b, alpha)
        elif len(s) == 6:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return (r, g, b, alpha)
        elif len(s) == 8:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            a = int(s[6:8], 16)
            return (r, g, b, a)
    except ValueError:
        pass
    return (255, 255, 255, alpha)


def round_corners(image: Image.Image, radius: int) -> Image.Image:
    """
    Aplica cantos arredondados à imagem usando supersampling 2x para antialiasing limpo.
    """
    if radius <= 0:
        return image.convert("RGBA")

    im = image.convert("RGBA")
    w, h = im.size
    scale = 2
    mask = Image.new("L", (w * scale, h * scale), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, w * scale - 1, h * scale - 1], radius=radius * scale, fill=255)
    mask = mask.resize((w, h), resample=Image.Resampling.LANCZOS)

    im.putalpha(mask)
    return im


def apply_border_outline(
    image: Image.Image,
    border_width: int,
    border_color: Tuple[int, int, int, int],
    radius: int
) -> Image.Image:
    """
    Desenha uma borda suave contornando o retângulo com ou sem cantos arredondados.
    """
    if border_width <= 0:
        return image

    im = image.convert("RGBA").copy()
    w, h = im.size
    scale = 2
    overlay = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    scaled_bw = border_width * scale
    scaled_rad = radius * scale
    half_bw = scaled_bw / 2.0

    rect = [
        half_bw,
        half_bw,
        w * scale - 1 - half_bw,
        h * scale - 1 - half_bw
    ]

    draw.rounded_rectangle(
        rect,
        radius=scaled_rad,
        outline=border_color,
        width=scaled_bw
    )

    overlay = overlay.resize((w, h), resample=Image.Resampling.LANCZOS)
    return Image.alpha_composite(im, overlay)


def create_linear_gradient(
    width: int,
    height: int,
    start_rgb: Tuple[int, int, int],
    end_rgb: Tuple[int, int, int]
) -> Image.Image:
    """Gera um fundo com gradiente linear vertical suave."""
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    return base


def compose_mockup(
    image: Image.Image,
    corner_radius: int = 16,
    border_width: int = 1,
    border_hex: str = "#d0d7de",
    shadow_blur: int = 24,
    shadow_offset_y: int = 12,
    shadow_opacity: float = 0.35,
    padding: int = 40,
    background_mode: str = "transparent",
    bg_color_hex: str = "#f6f8fa",
    gradient_preset: Optional[str] = None
) -> Image.Image:
    """
    Aplica composição completa de mockup: cantos arredondados, borda, sombra e fundo.
    """
    # 1. Cantos arredondados
    rounded = round_corners(image, corner_radius)

    # 2. Borda
    b_color = parse_hex_color(border_hex)
    framed = apply_border_outline(rounded, border_width, b_color, corner_radius)

    img_w, img_h = framed.size

    # 3. Canvas e Sombra
    total_padding_x = padding + (shadow_blur * 2)
    total_padding_y = padding + (shadow_blur * 2) + abs(shadow_offset_y)

    canvas_w = img_w + total_padding_x * 2
    canvas_h = img_h + total_padding_y * 2

    # Cria fundo base
    if background_mode == "color":
        bg_color = parse_hex_color(bg_color_hex)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), bg_color)
    elif background_mode == "gradient":
        gradients = {
            "slate": ((30, 41, 59), (15, 23, 42)),
            "sunset": ((255, 94, 98), (255, 153, 102)),
            "ocean": ((33, 147, 176), (109, 213, 250)),
            "purple": ((138, 35, 135), (233, 64, 87)),
            "minimal_gray": ((245, 247, 250), ((228, 232, 238))),
        }
        start_c, end_c = gradients.get(gradient_preset or "minimal_gray", gradients["minimal_gray"])
        canvas = create_linear_gradient(canvas_w, canvas_h, start_c, end_c)
    else:
        # Transparente
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Desenha Sombra Difusa (Drop Shadow)
    img_x = (canvas_w - img_w) // 2
    img_y = ((canvas_h - img_h) // 2) - (shadow_offset_y // 2)

    if shadow_blur > 0 and shadow_opacity > 0:
        shadow_mask = Image.new("L", (canvas_w, canvas_h), 0)
        s_draw = ImageDraw.Draw(shadow_mask)
        s_left = img_x
        s_top = img_y + shadow_offset_y
        s_draw.rounded_rectangle(
            [s_left, s_top, s_left + img_w - 1, s_top + img_h - 1],
            radius=corner_radius,
            fill=int(255 * max(0.0, min(1.0, shadow_opacity)))
        )
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(shadow_blur))

        shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        shadow_layer.putalpha(shadow_mask)
        canvas = Image.alpha_composite(canvas, shadow_layer)

    # Sobrepõe a imagem principal no centro
    canvas.paste(framed, (img_x, img_y), framed)
    return canvas


def process_image_border_shadow(
    input_path: Path,
    output_path: Path,
    corner_radius: int = 16,
    border_width: int = 1,
    border_hex: str = "#d0d7de",
    shadow_blur: int = 24,
    shadow_offset_y: int = 12,
    shadow_opacity: float = 0.35,
    padding: int = 40,
    background_mode: str = "transparent",
    bg_color_hex: str = "#f6f8fa",
    gradient_preset: Optional[str] = None
) -> Path:
    """
    Processa um arquivo de imagem aplicando o efeito de borda, sombra e mockup.
    """
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as im:
        result = compose_mockup(
            image=im,
            corner_radius=corner_radius,
            border_width=border_width,
            border_hex=border_hex,
            shadow_blur=shadow_blur,
            shadow_offset_y=shadow_offset_y,
            shadow_opacity=shadow_opacity,
            padding=padding,
            background_mode=background_mode,
            bg_color_hex=bg_color_hex,
            gradient_preset=gradient_preset
        )

        out_ext = output_path.suffix.lower()
        if out_ext in (".jpg", ".jpeg"):
            # Converte para RGB substituindo alfa por branco ou cor de fundo
            rgb_bg = Image.new("RGB", result.size, (255, 255, 255))
            rgb_bg.paste(result, mask=result.split()[3])
            rgb_bg.save(output_path, "JPEG", quality=95)
        elif out_ext == ".webp":
            result.save(output_path, "WEBP", quality=95)
        else:
            result.save(output_path, "PNG")

    return output_path
