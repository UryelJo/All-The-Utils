"""
Lógica pura de extração de paleta de cores dominantes em imagens.
"""
import colorsys
import json
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image, ImageDraw

def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Converte tupla RGB para formato hexadecimal #RRGGBB."""
    return f"#{r:02X}{g:02X}{b:02X}"

def rgb_to_hsl(r: int, g: int, b: int) -> str:
    """Converte RGB (0-255) para string HSL formatada."""
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return f"hsl({int(h * 360)}, {int(s * 100)}%, {int(l * 100)}%)"

def extract_dominant_colors(image_path: Path, num_colors: int = 6) -> List[Dict[str, Any]]:
    """Extrai as cores dominantes da imagem ordenadas por frequência relativa."""
    num_colors = max(2, min(16, num_colors))

    with Image.open(image_path) as im:
        # Reduz imagem para processamento rápido (máx 250x250)
        im_small = im.convert("RGB")
        im_small.thumbnail((250, 250), Image.Resampling.BILINEAR)

        total_pixels = im_small.size[0] * im_small.size[1]

        # Quantiza para encontrar as cores principais
        im_quant = im_small.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
        palette = im_quant.getpalette()  # lista plana [r, g, b, r, g, b...]
        colors_count = im_quant.getcolors()  # lista de (count, palette_index)

        if not colors_count or not palette:
            return []

        # Ordena pelo mais frequente
        colors_count.sort(key=lambda x: x[0], reverse=True)

        results = []
        for count, idx in colors_count:
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]

            pct = (count / float(total_pixels)) * 100.0
            results.append({
                "hex": rgb_to_hex(r, g, b),
                "rgb": (r, g, b),
                "rgb_str": f"rgb({r}, {g}, {b})",
                "hsl_str": rgb_to_hsl(r, g, b),
                "percent": round(pct, 1)
            })

        return results

def export_palette_css(colors: List[Dict[str, Any]]) -> str:
    """Gera bloco de variáveis CSS :root a partir da paleta."""
    lines = [":root {"]
    for idx, c in enumerate(colors, start=1):
        lines.append(f"  --color-{idx}: {c['hex']}; /* {c['rgb_str']} - {c['percent']}% */")
    lines.append("}")
    return "\n".join(lines)

def export_palette_json(colors: List[Dict[str, Any]]) -> str:
    """Gera representação JSON limpa da paleta."""
    data = {
        "palette": [
            {
                "hex": c["hex"],
                "rgb": list(c["rgb"]),
                "hsl": c["hsl_str"],
                "percent": c["percent"]
            }
            for c in colors
        ]
    }
    return json.dumps(data, indent=2, ensure_ascii=False)

def export_palette_image(colors: List[Dict[str, Any]], out_path: Path, width: int = 600, height: int = 120) -> None:
    """Gera uma imagem contendo as faixas horizontais de cada cor da paleta."""
    if not colors:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    im = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(im)

    num = len(colors)
    block_w = width / float(num)

    for idx, c in enumerate(colors):
        x0 = int(idx * block_w)
        x1 = int((idx + 1) * block_w) if idx < num - 1 else width
        draw.rectangle([x0, 0, x1, height], fill=c["rgb"])

    im.save(out_path, format="PNG")
