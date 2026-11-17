"""
Lógica pura para divisão de imagens em grade (NxM) e fatias verticais/horizontais.

Permite particionar imagens para carrossel do Instagram, mosaicos,
posters e atlas de sprites 2D com ou sem sobreposição (overlap).
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from wintoolbox.tools.images.convert.logic import ensure_heif_registered

ensure_heif_registered()

GRID_PRESETS: Dict[str, Optional[Dict[str, Any]]] = {
    "Personalizado": None,
    "Instagram Carrossel Retrato 1×2 (4:5)": {"rows": 1, "cols": 2, "aspect": (2 * 4, 5)},
    "Instagram Carrossel Retrato 1×3 (4:5)": {"rows": 1, "cols": 3, "aspect": (3 * 4, 5)},
    "Instagram Carrossel Retrato 1×4 (4:5)": {"rows": 1, "cols": 4, "aspect": (4 * 4, 5)},
    "Instagram Carrossel Retrato 1×5 (4:5)": {"rows": 1, "cols": 5, "aspect": (5 * 4, 5)},
    "Instagram Carrossel Retrato 1×6 (4:5)": {"rows": 1, "cols": 6, "aspect": (6 * 4, 5)},
    "Instagram Carrossel Retrato 1×10 (4:5)": {"rows": 1, "cols": 10, "aspect": (10 * 4, 5)},
    "Instagram Feed Quadrado 1×3 (1:1)": {"rows": 1, "cols": 3, "aspect": (3, 1)},
    "Instagram Mosaico de Perfil 3×3 (1:1)": {"rows": 3, "cols": 3, "aspect": (1, 1)},
    "Stories / Reels / TikTok 1×2 (9:16)": {"rows": 1, "cols": 2, "aspect": (2 * 9, 16)},
    "Stories / Reels / TikTok 1×3 (9:16)": {"rows": 1, "cols": 3, "aspect": (3 * 9, 16)},
    "YouTube / Banner Panorâmico 1×3 (16:9)": {"rows": 1, "cols": 3, "aspect": (3 * 16, 9)},
    "Post X / Twitter Grade 2×2": {"rows": 2, "cols": 2, "aspect": (1, 1)},
    "Poster A4 2×2 (4 Folhas)": {"rows": 2, "cols": 2, "aspect": (1, 1)},
    "Poster A4 3×3 (9 Folhas)": {"rows": 3, "cols": 3, "aspect": (1, 1)},
    "Sprite Atlas 2×2": {"rows": 2, "cols": 2, "aspect": None},
    "Sprite Atlas 4×4": {"rows": 4, "cols": 4, "aspect": None},
}


def calculate_grid_boxes(
    width: int,
    height: int,
    rows: int,
    cols: int,
    overlap_px: int = 0
) -> List[Tuple[int, int, int, int, int, int]]:
    """Calcula as coordenadas de corte (x1, y1, x2, y2) para cada célula da grade."""
    if rows < 1 or cols < 1:
        raise ValueError("Linhas e colunas devem ser maiores ou iguais a 1.")
    if width <= 0 or height <= 0:
        raise ValueError("Dimensões da imagem devem ser positivas.")

    step_w = width / cols
    step_h = height / rows

    tiles: List[Tuple[int, int, int, int, int, int]] = []

    for r in range(rows):
        y1_float = r * step_h
        y2_float = (r + 1) * step_h

        y1 = max(0, int(round(y1_float)) - (overlap_px if r > 0 else 0))
        y2 = min(height, int(round(y2_float)) + (overlap_px if r < rows - 1 else 0))

        for c in range(cols):
            x1_float = c * step_w
            x2_float = (c + 1) * step_w

            x1 = max(0, int(round(x1_float)) - (overlap_px if c > 0 else 0))
            x2 = min(width, int(round(x2_float)) + (overlap_px if c < cols - 1 else 0))

            tiles.append((r + 1, c + 1, x1, y1, x2, y2))

    return tiles


def split_image(
    image: Image.Image,
    rows: int,
    cols: int,
    overlap_px: int = 0
) -> List[Tuple[int, int, Image.Image]]:
    """Divide um objeto PIL Image em uma grade de imagens recortadas."""
    w, h = image.size
    boxes = calculate_grid_boxes(w, h, rows, cols, overlap_px)
    results: List[Tuple[int, int, Image.Image]] = []

    for r_idx, c_idx, x1, y1, x2, y2 in boxes:
        tile = image.crop((x1, y1, x2, y2))
        results.append((r_idx, c_idx, tile))

    return results


def render_grid_slice_preview(source_path: Path, params: Dict[str, Any]) -> Image.Image:
    """Gera pré-visualização dinâmica com as linhas de corte numeradas sobre a imagem."""
    with Image.open(source_path) as im:
        preview_im = im.convert("RGBA").copy()
        draw = ImageDraw.Draw(preview_im)
        w, h = preview_im.size

        rows = max(1, int(params.get("rows", 1)))
        cols = max(1, int(params.get("cols", 3)))
        overlap = int(params.get("overlap_px", 0))

        boxes = calculate_grid_boxes(w, h, rows, cols, overlap)

        font_size = max(16, min(w, h) // 18)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        line_w = max(2, min(w, h) // 250)
        tile_num = 1
        for r_idx, c_idx, x1, y1, x2, y2 in boxes:
            draw.rectangle([x1, y1, x2 - 1, y2 - 1], outline=(0, 180, 255, 230), width=line_w)

            # Badge do slide
            text = f"Slide {tile_num}"
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            badge_w = len(text) * (font_size // 2 + 2)
            badge_h = font_size + 10
            draw.rounded_rectangle(
                [cx - badge_w // 2, cy - badge_h // 2, cx + badge_w // 2, cy + badge_h // 2],
                radius=6,
                fill=(10, 15, 20, 180)
            )
            draw.text((cx, cy), text, fill=(255, 255, 255, 255), font=font, anchor="mm")
            tile_num += 1

        return preview_im


def process_image_split(
    input_path: Path,
    output_dir: Path,
    rows: int = 1,
    cols: int = 1,
    overlap_px: int = 0,
    output_format: str = "PNG",
    naming_pattern: str = "{stem}_row{row}_col{col}"
) -> List[Path]:
    """Processa um arquivo de imagem fatiando-o e gravando cada parte no diretório de saída."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_fmt = output_format.strip().upper().lstrip(".")
    ext = ".jpg" if out_fmt in ("JPG", "JPEG") else f".{out_fmt.lower()}"
    stem = input_path.stem

    generated_paths: List[Path] = []

    with Image.open(input_path) as im:
        tiles = split_image(im, rows, cols, overlap_px)

        for r_idx, c_idx, tile in tiles:
            filename = naming_pattern.format(stem=stem, row=r_idx, col=c_idx) + ext
            tile_path = output_dir / filename

            if ext in (".jpg", ".jpeg"):
                if tile.mode in ("RGBA", "LA", "P"):
                    rgb_bg = Image.new("RGB", tile.size, (255, 255, 255))
                    rgb_bg.paste(tile, mask=tile.split()[3] if "A" in tile.mode else None)
                    rgb_bg.save(tile_path, "JPEG", quality=95)
                else:
                    tile.save(tile_path, "JPEG", quality=95)
            elif ext == ".webp":
                tile.save(tile_path, "WEBP", quality=95)
            else:
                tile.save(tile_path, "PNG")

            generated_paths.append(tile_path)

    return generated_paths


# Alias para retrocompatibilidade
split_image_file = process_image_split
