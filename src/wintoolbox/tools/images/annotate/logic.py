"""
Lógica pura para edição e renderização de anotações sobre imagens.

Renderiza setas, formas geométricas, badges numerados de passos,
textos e desfoque/pixelização de regiões sensíveis utilizando Pillow.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("images.annotate.logic")


@dataclass
class AnnotationItem:
    """Item individual de anotação com tipo, coordenadas e estilo."""
    tool_type: str  # "arrow", "rect", "step", "text", "blur", "pixelate"
    coords: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    color: str = "#EF4444"
    width: int = 4
    text: str = ""
    step_num: int = 1
    font_size: int = 20

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_type": self.tool_type,
            "coords": self.coords,
            "color": self.color,
            "width": self.width,
            "text": self.text,
            "step_num": self.step_num,
            "font_size": self.font_size,
        }


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Converte código hex (#RRGGBB) em tupla RGB inteira."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    if len(hex_clean) != 6:
        return (239, 68, 68)  # Fallback vermelho
    try:
        return (
            int(hex_clean[0:2], 16),
            int(hex_clean[2:4], 16),
            int(hex_clean[4:6], 16),
        )
    except ValueError:
        return (239, 68, 68)


def pixelate_region(image: Image.Image, box: Tuple[int, int, int, int], block_size: int = 12) -> Image.Image:
    """Aplica pixelização (censura estilo mosaico) na região selecionada."""
    x1, y1, x2, y2 = box
    left = max(0, min(x1, x2))
    top = max(0, min(y1, y2))
    right = min(image.width, max(x1, x2))
    bottom = min(image.height, max(y1, y2))

    if right <= left or bottom <= top:
        return image

    crop_w = right - left
    crop_h = bottom - top

    # Reduz com interpolação bilinear para mesclar cores dos blocos e amplia com NEAREST
    region = image.crop((left, top, right, bottom))
    small_w = max(1, crop_w // block_size)
    small_h = max(1, crop_h // block_size)
    small = region.resize((small_w, small_h), resample=Image.BILINEAR)
    pixelated = small.resize((crop_w, crop_h), resample=Image.NEAREST)

    result = image.copy()
    result.paste(pixelated, (left, top))
    return result


def blur_region(image: Image.Image, box: Tuple[int, int, int, int], radius: int = 12) -> Image.Image:
    """Aplica desfoque gaussiano na região selecionada."""
    x1, y1, x2, y2 = box
    left = max(0, min(x1, x2))
    top = max(0, min(y1, y2))
    right = min(image.width, max(x1, x2))
    bottom = min(image.height, max(y1, y2))

    if right <= left or bottom <= top:
        return image

    region = image.crop((left, top, right, bottom))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))

    result = image.copy()
    result.paste(blurred, (left, top))
    return result


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: Tuple[int, int],
    end: Tuple[int, int],
    color_rgb: Tuple[int, int, int],
    width: int = 4
) -> None:
    """Desenha uma linha com cabeça de seta vetorial direcionada."""
    x1, y1 = start
    x2, y2 = end

    # Linha principal
    draw.line([start, end], fill=color_rgb, width=width)

    # Cálculo da cabeça da seta
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = max(15, width * 4)
    arrow_angle = math.pi / 6  # 30 graus

    left_x = x2 - arrow_len * math.cos(angle - arrow_angle)
    left_y = y2 - arrow_len * math.sin(angle - arrow_angle)
    right_x = x2 - arrow_len * math.cos(angle + arrow_angle)
    right_y = y2 - arrow_len * math.sin(angle + arrow_angle)

    # Desenha ponta preenchida
    draw.polygon([(x2, y2), (int(left_x), int(left_y)), (int(right_x), int(right_y))], fill=color_rgb)


def render_annotations(
    base_image: Image.Image,
    annotations: List[AnnotationItem]
) -> Image.Image:
    """
    Renderiza todas as anotações acumuladas sobre a imagem base.

    Args:
        base_image: Imagem original PIL.
        annotations: Lista de AnnotationItem em ordem cronológica.

    Returns:
        Nova imagem com todas as anotações aplicadas.
    """
    result = base_image.convert("RGBA").copy()

    # 1. Aplica filtros de imagem primeiro (desfoque e pixelização)
    for ann in annotations:
        if ann.tool_type == "pixelate":
            result = pixelate_region(result, ann.coords)
        elif ann.tool_type == "blur":
            result = blur_region(result, ann.coords)

    # 2. Desenha vetores e textos sobre a imagem resultante
    draw = ImageDraw.Draw(result)

    for ann in annotations:
        color_rgb = _hex_to_rgb(ann.color)
        x1, y1, x2, y2 = ann.coords
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        if ann.tool_type == "arrow":
            draw_arrow(draw, (x1, y1), (x2, y2), color_rgb, width=ann.width)

        elif ann.tool_type == "rect":
            draw.rectangle([left, top, right, bottom], outline=color_rgb, width=ann.width)

        elif ann.tool_type == "step":
            # Círculo badge com número de passo no centro
            cx, cy = x1, y1
            r = max(14, ann.width * 5)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color_rgb, outline=(255, 255, 255), width=2)

            num_str = str(ann.step_num)
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), num_str, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2 - 1), num_str, fill=(255, 255, 255), font=font)

        elif ann.tool_type == "text" and ann.text:
            font = ImageFont.load_default()
            bbox = draw.textbbox((left, top), ann.text, font=font)
            pad = 4
            # Fundo opaco para legibilidade
            draw.rectangle(
                [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                fill=(0, 0, 0, 180),
                outline=color_rgb,
                width=1
            )
            draw.text((left, top), ann.text, fill=(255, 255, 255), font=font)

    return result
