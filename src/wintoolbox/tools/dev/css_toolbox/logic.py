"""
Lógica pura para cálculos e geração de código CSS moderno.
Inclui gradientes, sombras box-shadow, tipografia fluida com clamp(), conversão px/rem e contraste WCAG.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import math
import re
from dataclasses import dataclass
from typing import List, Tuple


def calculate_fluid_clamp(
    min_size_px: float,
    max_size_px: float,
    min_viewport_px: float = 320.0,
    max_viewport_px: float = 1200.0,
    root_font_size: float = 16.0
) -> str:
    """
    Calcula a expressão CSS clamp() fluida para responsividade perfeita.
    Fórmula: clamp(min, intersection + slope * 100vw, max)
    """
    if min_viewport_px >= max_viewport_px:
        raise ValueError("A largura mínima de viewport deve ser menor que a máxima.")

    if min_size_px > max_size_px:
        min_size_px, max_size_px = max_size_px, min_size_px

    slope = (max_size_px - min_size_px) / (max_viewport_px - min_viewport_px)
    intersection_px = -min_viewport_px * slope + min_size_px

    min_rem = min_size_px / root_font_size
    max_rem = max_size_px / root_font_size
    intersection_rem = intersection_px / root_font_size
    slope_vw = slope * 100.0

    sign = "+" if slope_vw >= 0 else "-"
    abs_vw = abs(slope_vw)

    return f"clamp({min_rem:.4f}rem, {intersection_rem:.4f}rem {sign} {abs_vw:.4f}vw, {max_rem:.4f}rem)"


def px_to_rem(px: float, base_px: float = 16.0) -> float:
    """Converte pixels para rem."""
    if base_px <= 0:
        raise ValueError("A base de fonte deve ser maior que zero.")
    return px / base_px


def rem_to_px(rem: float, base_px: float = 16.0) -> float:
    """Converte rem para pixels."""
    return rem * base_px


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Converte código HEX (#RRGGBB ou #RGB) para tupla RGB."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        raise ValueError(f"Código HEX inválido: {hex_str}")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def get_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """
    Calcula a luminância relativa conforme a especificação W3C WCAG 2.1.
    """
    adjusted = []
    for c in rgb:
        val = c / 255.0
        if val <= 0.04045:
            adjusted.append(val / 12.92)
        else:
            adjusted.append(((val + 0.055) / 1.055) ** 2.4)
    r, g, b = adjusted
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(color_a_hex: str, color_b_hex: str) -> float:
    """
    Calcula a taxa de contraste (1:1 a 21:1) entre duas cores segundo WCAG 2.1.
    """
    rgb_a = hex_to_rgb(color_a_hex)
    rgb_b = hex_to_rgb(color_b_hex)

    lum_a = get_relative_luminance(rgb_a)
    lum_b = get_relative_luminance(rgb_b)

    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)

    return (lighter + 0.05) / (darker + 0.05)


def generate_linear_gradient_css(angle_deg: int, stops: List[Tuple[str, int]]) -> str:
    """Gera regra CSS de gradiente linear."""
    stops_str = ", ".join(f"{color} {pct}%" for color, pct in stops)
    return f"background: linear-gradient({angle_deg}deg, {stops_str});"


def generate_box_shadow_css(
    offset_x: int,
    offset_y: int,
    blur: int,
    spread: int,
    color_rgba: str,
    inset: bool = False
) -> str:
    """Gera regra CSS de sombra (box-shadow)."""
    inset_prefix = "inset " if inset else ""
    return f"box-shadow: {inset_prefix}{offset_x}px {offset_y}px {blur}px {spread}px {color_rgba};"
