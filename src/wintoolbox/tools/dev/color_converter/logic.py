"""
Lógica pura de conversão matemática de cores para desenvolvedores.
Suporta HEX, RGB, RGBA, HSL, HSLA, HSV, CMYK, Normalized e cálculo de contraste WCAG 2.1.
Zero acoplamento com interface gráfica.
"""
import colorsys
import math
import re
from typing import Any, Dict, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("dev.color_converter")


def parse_hex_color(hex_str: str) -> Tuple[int, int, int, float]:
    """Interpreta strings HEX (#RGB, #RGBA, #RRGGBB, #RRGGBBAA) retornando (R, G, B, Alpha)."""
    h = hex_str.strip().lstrip("#")
    if len(h) == 3:  # RGB
        r, g, b = (int(c * 2, 16) for c in h)
        return r, g, b, 1.0
    elif len(h) == 4:  # RGBA
        r, g, b = (int(c * 2, 16) for c in h[:3])
        a = round(int(h[3] * 2, 16) / 255.0, 2)
        return r, g, b, a
    elif len(h) == 6:  # RRGGBB
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return r, g, b, 1.0
    elif len(h) == 8:  # RRGGBBAA
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        a = round(int(h[6:8], 16) / 255.0, 2)
        return r, g, b, a
    raise ValueError(f"Formato HEX inválido: '{hex_str}'")


def rgb_to_hex(r: int, g: int, b: int, a: float = 1.0) -> str:
    """Converte valores RGB (0-255) e alpha (0.0-1.0) para HEX (#RRGGBB ou #RRGGBBAA)."""
    r_cl = max(0, min(255, int(r)))
    g_cl = max(0, min(255, int(g)))
    b_cl = max(0, min(255, int(b)))
    if a < 0.999:
        a_int = max(0, min(255, int(round(a * 255))))
        return f"#{r_cl:02X}{g_cl:02X}{b_cl:02X}{a_int:02X}"
    return f"#{r_cl:02X}{g_cl:02X}{b_cl:02X}"


def rgb_to_hsl(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """Converte RGB (0-255) para HSL (H: 0-360, S: 0-100%, L: 0-100%)."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    h, l, s = colorsys.rgb_to_hls(rf, gf, bf)
    return int(round(h * 360)), int(round(s * 100)), int(round(l * 100))


def hsl_to_rgb(h: int, s: int, l: int) -> Tuple[int, int, int]:
    """Converte HSL para RGB (0-255)."""
    hf = (h % 360) / 360.0
    sf = max(0.0, min(1.0, s / 100.0))
    lf = max(0.0, min(1.0, l / 100.0))
    rf, gf, bf = colorsys.hls_to_rgb(hf, lf, sf)
    return int(round(rf * 255)), int(round(gf * 255)), int(round(bf * 255))


def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """Converte RGB (0-255) para HSV/HSB (H: 0-360, S: 0-100%, V: 0-100%)."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
    return int(round(h * 360)), int(round(s * 100)), int(round(v * 100))


def hsv_to_rgb(h: int, s: int, v: int) -> Tuple[int, int, int]:
    """Converte HSV para RGB (0-255)."""
    hf = (h % 360) / 360.0
    sf = max(0.0, min(1.0, s / 100.0))
    vf = max(0.0, min(1.0, v / 100.0))
    rf, gf, bf = colorsys.hsv_to_rgb(hf, sf, vf)
    return int(round(rf * 255)), int(round(gf * 255)), int(round(bf * 255))


def rgb_to_cmyk(r: int, g: int, b: int) -> Tuple[int, int, int, int]:
    """Converte RGB (0-255) para CMYK (0-100%)."""
    if r == 0 and g == 0 and b == 0:
        return 0, 0, 0, 100
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    k = 1.0 - max(rf, gf, bf)
    c = (1.0 - rf - k) / (1.0 - k)
    m = (1.0 - gf - k) / (1.0 - k)
    y = (1.0 - bf - k) / (1.0 - k)
    return int(round(c * 100)), int(round(m * 100)), int(round(y * 100)), int(round(k * 100))


def cmyk_to_rgb(c: int, m: int, y: int, k: int) -> Tuple[int, int, int]:
    """Converte CMYK (0-100%) para RGB (0-255)."""
    cf, mf, yf, kf = c / 100.0, m / 100.0, y / 100.0, k / 100.0
    r = 255 * (1.0 - cf) * (1.0 - kf)
    g = 255 * (1.0 - mf) * (1.0 - kf)
    b = 255 * (1.0 - yf) * (1.0 - kf)
    return int(round(r)), int(round(g)), int(round(b))


def relative_luminance(r: int, g: int, b: int) -> float:
    """Calcula a luminância relativa conforme recomendação W3C WCAG 2.1."""
    def channel_val(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
    return 0.2126 * channel_val(r) + 0.7152 * channel_val(g) + 0.0722 * channel_val(b)


def contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """Calcula a razão de contraste entre duas cores (entre 1.0 e 21.0)."""
    l1 = relative_luminance(*rgb1)
    l2 = relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def get_all_color_formats(r: int, g: int, b: int, a: float = 1.0) -> Dict[str, Any]:
    """Consolida todas as representações de uma cor com trechos de código para desenvolvimento."""
    h_hex = rgb_to_hex(r, g, b, a)
    hsl_h, hsl_s, hsl_l = rgb_to_hsl(r, g, b)
    hsv_h, hsv_s, hsv_v = rgb_to_hsv(r, g, b)
    c, m, y, k = rgb_to_cmyk(r, g, b)

    contrast_white = contrast_ratio((r, g, b), (255, 255, 255))
    contrast_black = contrast_ratio((r, g, b), (0, 0, 0))

    # Trechos de código dev
    code_snippets = {
        "CSS HEX": h_hex,
        "CSS RGB": f"rgb({r}, {g}, {b})" if a >= 0.999 else f"rgba({r}, {g}, {b}, {a:.2f})",
        "CSS HSL": f"hsl({hsl_h}, {hsl_s}%, {hsl_l}%)" if a >= 0.999 else f"hsla({hsl_h}, {hsl_s}%, {hsl_l}%, {a:.2f})",
        "Tailwind": f"bg-[{h_hex.lower()}]",
        "Python (RGB)": f"({r}, {g}, {b})",
        "Python (RGBA)": f"({r}, {g}, {b}, {a:.2f})",
        "Normalized": f"({r/255.0:.3f}, {g/255.0:.3f}, {b/255.0:.3f}, {a:.2f})",
        "Android / Flutter (HEX)": f"0xFF{r:02X}{g:02X}{b:02X}",
        "Unity C#": f"new Color({r/255.0:.3f}f, {g/255.0:.3f}f, {b/255.0:.3f}f, {a:.2f}f)"
    }

    return {
        "r": r, "g": g, "b": b, "a": a,
        "hex": h_hex,
        "hsl": (hsl_h, hsl_s, hsl_l),
        "hsv": (hsv_h, hsv_s, hsv_v),
        "cmyk": (c, m, y, k),
        "contrast_white": contrast_white,
        "contrast_black": contrast_black,
        "wcag_white_aa": contrast_white >= 4.5,
        "wcag_black_aa": contrast_black >= 4.5,
        "code_snippets": code_snippets
    }
