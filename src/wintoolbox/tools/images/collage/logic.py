"""
Lógica pura para criação de colagens e montagens de imagens em grade via Pillow.
Isolada de qualquer interface gráfica.
"""
import math
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageOps


def create_image_collage(
    image_paths: List[Path],
    output_path: Path,
    cols: int = 2,
    spacing: int = 12,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    cell_size: Tuple[int, int] = (450, 450),
    fit_mode: str = "crop"
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

    # Cria canvas com a cor de fundo escolhida
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    for idx, img_path in enumerate(valid_paths):
        r = idx // cols
        c = idx % cols
        pos_x = spacing + (c * (cell_w + spacing))
        pos_y = spacing + (r * (cell_h + spacing))

        with Image.open(img_path) as img_raw:
            # Normaliza orientação EXIF
            img = ImageOps.exif_transpose(img_raw).convert("RGB")
            orig_w, orig_h = img.size

            if fit_mode == "crop":
                # Corta e preenche exatamente o quadrado da célula
                cell_img = ImageOps.fit(img, (cell_w, cell_h), method=Image.Resampling.LANCZOS)
            else:
                # Ajusta proporcionalmente (fit) centralizado sobre fundo da cor bg_color
                ratio = min(cell_w / orig_w, cell_h / orig_h)
                new_w = max(1, int(orig_w * ratio))
                new_h = max(1, int(orig_h * ratio))
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                cell_img = Image.new("RGB", (cell_w, cell_h), bg_color)
                off_x = (cell_w - new_w) // 2
                off_y = (cell_h - new_h) // 2
                cell_img.paste(resized, (off_x, off_y))

            canvas.paste(cell_img, (pos_x, pos_y))

    # Determina formato e qualidade de salvamento
    ext = output_path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        canvas.save(output_path, "JPEG", quality=92, optimize=True)
    else:
        canvas.save(output_path, "PNG", optimize=True)

    return output_path
