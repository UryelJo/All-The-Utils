"""
Lógica pura para captura de tela e desenho de anotações sobre imagens via Pillow.
Isolada de qualquer interface gráfica.
"""
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageGrab


def capture_screen_image(bbox: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """
    Captura a tela inteira ou uma região retangular específica (x1, y1, x2, y2).
    """
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    return img.convert("RGB")


def apply_annotations_to_image(
    base_image: Image.Image,
    rectangles: Optional[List[Tuple[int, int, int, int, str, int]]] = None,
    texts: Optional[List[Tuple[int, int, str, str, int]]] = None
) -> Image.Image:
    """
    Aplica anotações gráficas (retângulos destacados e textos) sobre uma cópia da imagem.
    rectangles: lista de (x1, y1, x2, y2, color_hex, stroke_width)
    texts: lista de (x, y, text, color_hex, font_size)
    """
    canvas = base_image.copy()
    draw = ImageDraw.Draw(canvas)

    if rectangles:
        for x1, y1, x2, y2, color_hex, width in rectangles:
            draw.rectangle([x1, y1, x2, y2], outline=color_hex, width=max(1, width))

    if texts:
        for x, y, text_str, color_hex, size in texts:
            try:
                font = ImageFont.truetype("arial.ttf", size=max(10, size))
            except Exception:
                font = ImageFont.load_default()
            draw.text((x, y), text_str, fill=color_hex, font=font)

    return canvas


def save_screenshot(
    image: Image.Image,
    output_path: Path,
    format: str = "PNG"
) -> Path:
    """
    Salva a imagem capturada em disco no formato especificado.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = format.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    image.save(output_path, format=fmt, quality=95)
    return output_path
