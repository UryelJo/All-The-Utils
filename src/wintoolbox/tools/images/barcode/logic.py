"""
Lógica pura para geração e exportação de códigos de barras lineares (1D).

Suporta os padrões industriais mais utilizados:
- Code128 (alfanumérico de alta densidade)
- EAN-13 e EAN-8 (varejo e produtos comerciais)
- Standard 39 / Code 39 (logística e automação)
- Interleaved 2 of 5 / I2of5 (caixas e transporte)
- UPC-A (comércio norte-americano)

Gera imagens raster de alta definição (PNG) e vetores limpos (SVG).
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from pathlib import Path
from typing import Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics.shapes import Group, Rect, String
from reportlab.graphics import renderSVG

SUPPORTED_BARCODE_FORMATS = [
    "Code128",
    "EAN13",
    "EAN8",
    "I2of5",
    "Standard39",
    "UPCA",
]


def validate_barcode_input(format_name: str, value: str) -> str:
    """
    Valida e normaliza o valor de entrada para o formato de código de barras especificado.

    Raises:
        ValueError: se a entrada não for compatível com as regras do formato.
    """
    val = value.strip()
    if not val:
        raise ValueError("O valor do código de barras não pode ser vazio.")

    fmt = format_name.upper().replace("-", "")

    if fmt == "EAN13":
        digits = "".join(ch for ch in val if ch.isdigit())
        if len(digits) not in (12, 13):
            raise ValueError(f"EAN-13 requer 12 ou 13 dígitos numéricos (recebido: {len(digits)}).")
        return digits[:12] if len(digits) == 12 else digits

    elif fmt == "EAN8":
        digits = "".join(ch for ch in val if ch.isdigit())
        if len(digits) not in (7, 8):
            raise ValueError(f"EAN-8 requer 7 ou 8 dígitos numéricos (recebido: {len(digits)}).")
        return digits[:7] if len(digits) == 7 else digits

    elif fmt == "UPCA":
        digits = "".join(ch for ch in val if ch.isdigit())
        if len(digits) not in (11, 12):
            raise ValueError(f"UPC-A requer 11 ou 12 dígitos numéricos (recebido: {len(digits)}).")
        return digits[:11] if len(digits) == 11 else digits

    elif fmt == "I2OF5":
        digits = "".join(ch for ch in val if ch.isdigit())
        if not digits:
            raise ValueError("I2of5 (Interleaved 2 of 5) requer dígitos numéricos.")
        if len(digits) % 2 != 0:
            digits = "0" + digits
        return digits

    elif fmt in ("STANDARD39", "CODE39"):
        cleaned = val.upper()
        allowed = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ -.$/+%")
        if not all(c in allowed for c in cleaned):
            raise ValueError("Code 39 suporta apenas maiúsculas, dígitos e caracteres: - . $ / + % espaço.")
        return cleaned

    return val


def _collect_shapes(node: Any, shape_list: List[Any]) -> None:
    """Extrai recursivamente todos os nós elementares de um nó ou grupo gráfico."""
    if hasattr(node, "draw") and callable(node.draw) and not isinstance(node, Group):
        try:
            drawn = node.draw()
            if drawn is not None and drawn is not node:
                _collect_shapes(drawn, shape_list)
                return
        except Exception:
            pass

    if hasattr(node, "getContents"):
        for child in node.getContents():
            _collect_shapes(child, shape_list)
    else:
        shape_list.append(node)


def generate_barcode_image(
    format_name: str,
    value: str,
    bar_width: int = 3,
    bar_height: int = 120,
    quiet_zone: int = 30,
    show_text: bool = True
) -> Image.Image:
    """
    Renderiza um código de barras em imagem PIL formato RGBA a partir das formas vetoriais.
    """
    norm_val = validate_barcode_input(format_name, value)
    bw_pt = max(1.0, float(bar_width))
    bh_pt = max(30.0, float(bar_height))

    drawing = createBarcodeDrawing(
        format_name,
        value=norm_val,
        barWidth=bw_pt,
        barHeight=bh_pt,
        humanReadable=show_text
    )
    if not drawing or not drawing.getContents():
        raise ValueError(f"Não foi possível construir o desenho de código de barras para '{format_name}'.")

    shapes: List[Any] = []
    _collect_shapes(drawing, shapes)

    rects = [
        s for s in shapes
        if isinstance(s, Rect) and getattr(s, "fillColor", None) is not None
    ]
    strings = [s for s in shapes if isinstance(s, String)]

    if not rects:
        raise ValueError("Nenhuma barra foi gerada para o código especificado.")

    min_x = min(r.x for r in rects)
    max_x = max(r.x + r.width for r in rects)
    min_y = min(r.y for r in rects)
    max_y = max(r.y + r.height for r in rects)

    content_w = int(max_x - min_x)
    content_h = int(max_y - min_y)

    canvas_w = content_w + (quiet_zone * 2)
    text_space = 25 if (show_text and strings) else 0
    canvas_h = content_h + (quiet_zone * 2) + text_space

    img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Desenha barras (inversão de coordenadas PostScript/PDF para tela)
    for r in rects:
        rx = quiet_zone + int(r.x - min_x)
        rw = max(1, int(r.width))
        ry = quiet_zone + int(max_y - (r.y + r.height))
        rh = int(r.height)
        draw.rectangle([rx, ry, rx + rw - 1, ry + rh - 1], fill=(0, 0, 0, 255))

    # Desenha textos legíveis
    if show_text and strings:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        for s in strings:
            sx = quiet_zone + int(s.x - min_x)
            sy = quiet_zone + int(max_y - s.y) + 4
            draw.text((sx, sy), s.text, fill=(0, 0, 0, 255), font=font)

    return img


def generate_barcode_svg(
    format_name: str,
    value: str,
    bar_width: float = 1.0,
    bar_height: float = 50.0
) -> str:
    """
    Gera string XML contendo o SVG vetorial do código de barras.
    """
    norm_val = validate_barcode_input(format_name, value)
    drawing = createBarcodeDrawing(
        format_name,
        value=norm_val,
        barWidth=bar_width,
        barHeight=bar_height,
        humanReadable=True
    )
    return renderSVG.drawToString(drawing)


def save_barcode_file(
    format_name: str,
    value: str,
    output_path: Path,
    bar_width: int = 3,
    bar_height: int = 120,
    show_text: bool = True
) -> Path:
    """
    Gera e salva o código de barras no caminho de destino (PNG ou SVG conforme extensão).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ext = output_path.suffix.lower()

    if ext == ".svg":
        svg_content = generate_barcode_svg(format_name, value, bar_width=float(bar_width), bar_height=float(bar_height))
        output_path.write_text(svg_content, encoding="utf-8")
    else:
        img = generate_barcode_image(format_name, value, bar_width=bar_width, bar_height=bar_height, show_text=show_text)
        img.save(output_path, "PNG")

    return output_path
