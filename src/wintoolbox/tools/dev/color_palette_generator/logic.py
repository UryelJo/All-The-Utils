"""
Lógica pura para geração de paletas harmônicas de cores e cálculo de contraste de acessibilidade WCAG.
Implementa transformações esféricas no círculo cromático HSL (Complementar, Análoga, Triádica, Monocromática)
e equações oficiais de luminância relativa sRGB (WCAG 2.1).

Zero dependências de interface gráfica.
"""
import colorsys
import json
import re
from typing import Any, Dict, List, Tuple


def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Converte string hex '#RRGGBB' ou 'RRGGBB' para tupla (r, g, b) no intervalo 0-255."""
    clean = hex_code.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        raise ValueError(f"Código HEX inválido: '{hex_code}' (esperado 3 ou 6 dígitos)")
    try:
        r = int(clean[0:2], 16)
        g = int(clean[2:4], 16)
        b = int(clean[4:6], 16)
        return r, g, b
    except ValueError as exc:
        raise ValueError(f"Dígitos hexadecimais inválidos em '{hex_code}'") from exc


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Converte tupla (r, g, b) para string '#RRGGBB' em maiúsculas."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"#{r:02X}{g:02X}{b:02X}"


def rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Converte RGB (0-255) para HSL (H: 0-360, S: 0-1, L: 0-1)."""
    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
    h_norm, l_norm, s_norm = colorsys.rgb_to_hls(r_norm, g_norm, b_norm)
    return round(h_norm * 360, 1), round(s_norm, 3), round(l_norm, 3)


def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    """Converte HSL (H: 0-360, S: 0-1, L: 0-1) para RGB (0-255)."""
    h_norm = (h % 360) / 360.0
    s_norm = max(0.0, min(1.0, s))
    l_norm = max(0.0, min(1.0, l))
    r_norm, g_norm, b_norm = colorsys.hls_to_rgb(h_norm, l_norm, s_norm)
    return round(r_norm * 255), round(g_norm * 255), round(b_norm * 255)


def calculate_relative_luminance(r: int, g: int, b: int) -> float:
    """
    Calcula a luminância relativa sRGB segundo a fórmula oficial WCAG 2.1.
    """
    def adjust(channel: int) -> float:
        c = channel / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rs = adjust(r)
    gs = adjust(g)
    bs = adjust(b)
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs


def calculate_contrast_ratio(hex1: str, hex2: str) -> Dict[str, Any]:
    """
    Calcula a razão de contraste entre duas cores e valida conformidade WCAG AA e AAA.
    """
    r1, g1, b1 = hex_to_rgb(hex1)
    r2, g2, b2 = hex_to_rgb(hex2)

    lum1 = calculate_relative_luminance(r1, g1, b1)
    lum2 = calculate_relative_luminance(r2, g2, b2)

    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)

    ratio = (lighter + 0.05) / (darker + 0.05)
    rounded_ratio = round(ratio, 2)

    return {
        "ratio": rounded_ratio,
        "ratio_str": f"{rounded_ratio}:1",
        "wcag_aa_normal": rounded_ratio >= 4.5,
        "wcag_aa_large": rounded_ratio >= 3.0,
        "wcag_aaa_normal": rounded_ratio >= 7.0,
        "wcag_aaa_large": rounded_ratio >= 4.5,
    }


def generate_palette(base_hex: str, harmony_mode: str = "complementary") -> List[Dict[str, Any]]:
    """
    Gera uma paleta harmônica a partir da cor base.
    Modos: 'complementary', 'analogous', 'triadic', 'tetradic', 'monochromatic', 'split_complementary'.
    """
    r, g, b = hex_to_rgb(base_hex)
    h, s, l = rgb_to_hsl(r, g, b)

    hues: List[Tuple[float, float, float, str]] = []
    mode = harmony_mode.lower().strip()

    if mode == "complementary":
        hues = [
            (h, s, l, "Base"),
            ((h + 180) % 360, s, l, "Complementar"),
            (h, s, max(0.1, l - 0.2), "Sombra Base"),
            ((h + 180) % 360, s, min(0.9, l + 0.2), "Luz Complementar"),
        ]

    elif mode == "analogous":
        hues = [
            ((h - 30) % 360, s, l, "Análoga -30°"),
            (h, s, l, "Base"),
            ((h + 30) % 360, s, l, "Análoga +30°"),
            ((h + 60) % 360, s, l, "Análoga +60°"),
        ]

    elif mode == "triadic":
        hues = [
            (h, s, l, "Base"),
            ((h + 120) % 360, s, l, "Triádica 1 (+120°)"),
            ((h + 240) % 360, s, l, "Triádica 2 (+240°)"),
        ]

    elif mode == "tetradic":
        hues = [
            (h, s, l, "Base"),
            ((h + 90) % 360, s, l, "Tétrade +90°"),
            ((h + 180) % 360, s, l, "Tétrade +180°"),
            ((h + 270) % 360, s, l, "Tétrade +270°"),
        ]

    elif mode == "monochromatic":
        hues = [
            (h, s, max(0.1, l - 0.3), "Muito Escuro"),
            (h, s, max(0.2, l - 0.15), "Escuro"),
            (h, s, l, "Base"),
            (h, s, min(0.85, l + 0.15), "Claro"),
            (h, s, min(0.95, l + 0.3), "Muito Claro"),
        ]

    elif mode == "split_complementary":
        hues = [
            (h, s, l, "Base"),
            ((h + 150) % 360, s, l, "Split +150°"),
            ((h + 210) % 360, s, l, "Split +210°"),
        ]
    else:
        hues = [(h, s, l, "Base")]

    palette = []
    for cur_h, cur_s, cur_l, label in hues:
        c_r, c_g, c_b = hsl_to_rgb(cur_h, cur_s, cur_l)
        c_hex = rgb_to_hex(c_r, c_g, c_b)
        contrast_white = calculate_contrast_ratio(c_hex, "#FFFFFF")
        contrast_black = calculate_contrast_ratio(c_hex, "#000000")

        palette.append({
            "label": label,
            "hex": c_hex,
            "rgb": f"rgb({c_r}, {c_g}, {c_b})",
            "hsl": f"hsl({cur_h:.0f}, {cur_s*100:.0f}%, {cur_l*100:.0f}%)",
            "contrast_on_white": contrast_white["ratio_str"],
            "contrast_on_black": contrast_black["ratio_str"],
            "wcag_aa_white": contrast_white["wcag_aa_normal"],
            "wcag_aa_black": contrast_black["wcag_aa_normal"],
        })

    return palette


def export_palette_code(palette: List[Dict[str, Any]], format_type: str = "css") -> str:
    """Exporta a paleta gerada como variáveis CSS, SCSS ou JSON."""
    fmt = format_type.lower().strip()
    if fmt == "css":
        lines = [":root {"]
        for idx, item in enumerate(palette):
            clean_name = re.sub(r"[^a-zA-Z0-9]+", "-", item["label"].lower()).strip("-")
            lines.append(f"  --color-{clean_name}: {item['hex']};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    elif fmt == "scss":
        lines = []
        for idx, item in enumerate(palette):
            clean_name = re.sub(r"[^a-zA-Z0-9]+", "-", item["label"].lower()).strip("-")
            lines.append(f"$color-{clean_name}: {item['hex']};")
        return "\n".join(lines) + "\n"

    elif fmt == "json":
        return json.dumps(palette, indent=2, ensure_ascii=False)

    return ""
