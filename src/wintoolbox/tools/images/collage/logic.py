"""
Lógica pura para criação de colagens, montagens e gerador de templates via Pillow.
Inclui algoritmo de detecção automática de caixas de fotos por cor-chave (chroma)
e preenchimento de templates personalizados (.wtpl.json).
"""
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageOps


def create_image_collage(
    image_paths: List[Path],
    output_path: Path,
    cols: int = 2,
    spacing: int = 12,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    cell_size: Tuple[int, int] = (450, 450),
    fit_mode: str = "crop",
    output_format: str = "PNG"
) -> Path:
    """
    Combina uma lista de imagens em uma grade uniforme organizada em colunas e linhas.
    """
    valid_paths = [Path(p) for p in image_paths if Path(p).is_file()]
    if not valid_paths:
        raise ValueError("Nenhuma imagem válida fornecida para a colagem.")

    total_images = len(valid_paths)
    cols = max(1, min(cols, total_images))
    rows = math.ceil(total_images / cols)

    cell_w, cell_h = cell_size
    canvas_w = (cols * cell_w) + ((cols + 1) * spacing)
    canvas_h = (rows * cell_h) + ((rows + 1) * spacing)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    for idx, img_path in enumerate(valid_paths):
        r = idx // cols
        c = idx % cols
        pos_x = spacing + (c * (cell_w + spacing))
        pos_y = spacing + (r * (cell_h + spacing))

        with Image.open(img_path) as img_raw:
            img = ImageOps.exif_transpose(img_raw).convert("RGB")
            orig_w, orig_h = img.size

            if fit_mode == "crop":
                cell_img = ImageOps.fit(img, (cell_w, cell_h), method=Image.Resampling.LANCZOS)
            else:
                ratio = min(cell_w / orig_w, cell_h / orig_h)
                new_w = max(1, int(orig_w * ratio))
                new_h = max(1, int(orig_h * ratio))
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                cell_img = Image.new("RGB", (cell_w, cell_h), bg_color)
                off_x = (cell_w - new_w) // 2
                off_y = (cell_h - new_h) // 2
                cell_img.paste(resized, (off_x, off_y))

            canvas.paste(cell_img, (pos_x, pos_y))

    fmt = output_format.strip().upper().lstrip(".")
    if fmt in ("JPG", "JPEG"):
        canvas.save(output_path, "JPEG", quality=92, optimize=True)
    elif fmt == "WEBP":
        canvas.save(output_path, "WEBP", quality=90)
    else:
        canvas.save(output_path, "PNG", optimize=True)

    return output_path


def detect_chroma_slots(
    template_image_path: Path,
    chroma_hex: str = "#00FF00",
    tolerance: int = 45,
    min_area_px: int = 2500
) -> List[Tuple[int, int, int, int]]:
    """
    Detecta automaticamente caixas delimitadoras (x1, y1, x2, y2) de regiões marcadas
    com a cor chroma (ex: verde #00FF00) na arte de template.
    Usa amostragem rápida e flood-fill para encontrar componentes conexos.
    """
    if not template_image_path.is_file():
        raise FileNotFoundError(f"Template não encontrado: {template_image_path}")

    # Parse chroma color
    c = chroma_hex.strip().lstrip("#")
    cr, cg, cb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    with Image.open(template_image_path) as im:
        orig_w, orig_h = im.size
        # Reduz escala para velocidade na busca conexa
        scale = 4 if max(orig_w, orig_h) > 1200 else 2
        thumb = im.resize((orig_w // scale, orig_h // scale), Image.Resampling.BILINEAR).convert("RGB")
        tw, th = thumb.size
        pix = thumb.load()

        # Cria máscara binária
        mask = [[False] * tw for _ in range(th)]
        for y in range(th):
            for x in range(tw):
                r, g, b = pix[x, y]
                dist = math.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)
                if dist <= tolerance:
                    mask[y][x] = True

        # Flood fill para encontrar caixas conectadas
        visited = [[False] * tw for _ in range(th)]
        boxes: List[Tuple[int, int, int, int]] = []

        for y in range(th):
            for x in range(tw):
                if mask[y][x] and not visited[y][x]:
                    # BFS
                    min_x, max_x = x, x
                    min_y, max_y = y, y
                    count = 0
                    queue = [(x, y)]
                    visited[y][x] = True

                    while queue:
                        cx, cy = queue.pop(0)
                        count += 1
                        min_x = min(min_x, cx)
                        max_x = max(max_x, cx)
                        min_y = min(min_y, cy)
                        max_y = max(max_y, cy)

                        for nx, ny in [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]:
                            if 0 <= nx < tw and 0 <= ny < th and mask[ny][nx] and not visited[ny][nx]:
                                visited[ny][nx] = True
                                queue.append((nx, ny))

                    # Converte de volta para escala original
                    orig_min_x = max(0, min_x * scale)
                    orig_min_y = max(0, min_y * scale)
                    orig_max_x = min(orig_w, (max_x + 1) * scale)
                    orig_max_y = min(orig_h, (max_y + 1) * scale)
                    area = (orig_max_x - orig_min_x) * (orig_max_y - orig_min_y)

                    if area >= min_area_px:
                        boxes.append((orig_min_x, orig_min_y, orig_max_x, orig_max_y))

    # Ordena caixas (de cima para baixo, da esquerda para a direita)
    boxes.sort(key=lambda b: (b[1] // 100, b[0]))
    return boxes


def render_template_collage(
    base_image_path: Path,
    slots: List[Dict[str, Any]],
    slot_photos: Dict[int, Path],
    output_path: Path,
    output_format: str = "PNG"
) -> Path:
    """Preenche os slots de um template com as fotos fornecidas e grava o arquivo final."""
    with Image.open(base_image_path) as base_im:
        canvas = base_im.convert("RGBA").copy()

        for slot in slots:
            slot_id = slot["id"]
            if slot_id not in slot_photos or not Path(slot_photos[slot_id]).is_file():
                continue

            x1, y1, x2, y2 = slot["rect"]
            box_w = max(10, x2 - x1)
            box_h = max(10, y2 - y1)
            radius = int(slot.get("corner_radius", 0))

            photo_path = Path(slot_photos[slot_id])
            with Image.open(photo_path) as photo_im:
                photo = ImageOps.exif_transpose(photo_im).convert("RGBA")
                fitted = ImageOps.fit(photo, (box_w, box_h), method=Image.Resampling.LANCZOS)

                if radius > 0:
                    mask = Image.new("L", (box_w, box_h), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.rounded_rectangle([0, 0, box_w - 1, box_h - 1], radius=radius, fill=255)
                    fitted.putalpha(mask)

                canvas.paste(fitted, (x1, y1), fitted)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = output_format.strip().upper().lstrip(".")

    if fmt in ("JPG", "JPEG"):
        rgb_canvas = Image.new("RGB", canvas.size, (255, 255, 255))
        rgb_canvas.paste(canvas, mask=canvas.split()[3])
        rgb_canvas.save(output_path, "JPEG", quality=92, optimize=True)
    elif fmt == "WEBP":
        canvas.save(output_path, "WEBP", quality=90)
    else:
        canvas.save(output_path, "PNG", optimize=True)

    return output_path
