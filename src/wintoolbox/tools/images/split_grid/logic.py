"""
Lógica pura para divisão de imagens em grade (NxM) e fatias verticais/horizontais.

Permite particionar imagens para carrossel do Instagram, mosaicos,
posters e atlas de sprites 2D com ou sem sobreposição (overlap).
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from wintoolbox.tools.images.convert.logic import ensure_heif_registered

ensure_heif_registered()


def calculate_grid_boxes(
    width: int,
    height: int,
    rows: int,
    cols: int,
    overlap_px: int = 0
) -> List[Tuple[int, int, int, int, int, int]]:
    """
    Calcula as coordenadas de corte (x1, y1, x2, y2) para cada célula da grade.

    Args:
        width: Largura total da imagem em pixels.
        height: Altura total da imagem em pixels.
        rows: Quantidade de divisões verticais (linhas >= 1).
        cols: Quantidade de divisões horizontais (colunas >= 1).
        overlap_px: Pixels de sobreposição nas margens comuns entre células adjacentes.

    Returns:
        Lista de tuplas (row_index, col_index, x1, y1, x2, y2).
    """
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
    """
    Divide um objeto PIL Image em uma grade de imagens recortadas.
    """
    w, h = image.size
    boxes = calculate_grid_boxes(w, h, rows, cols, overlap_px)
    results: List[Tuple[int, int, Image.Image]] = []

    for r_idx, c_idx, x1, y1, x2, y2 in boxes:
        tile = image.crop((x1, y1, x2, y2))
        results.append((r_idx, c_idx, tile))

    return results


def split_image_file(
    input_path: Path,
    output_dir: Path,
    rows: int = 1,
    cols: int = 3,
    overlap_px: int = 0,
    output_format: str = "png"
) -> List[Path]:
    """
    Abre o arquivo de imagem, divide na grade e grava as partes numeradas na pasta de destino.
    """
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = input_path.stem
    fmt = output_format.lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"

    saved_files: List[Path] = []

    with Image.open(input_path) as im:
        tiles = split_image(im, rows, cols, overlap_px)
        is_single_row = (rows == 1)
        is_single_col = (cols == 1)

        for r_idx, c_idx, tile_img in tiles:
            if is_single_row:
                file_name = f"{base_name}_part_{c_idx:02d}.{fmt}"
            elif is_single_col:
                file_name = f"{base_name}_part_{r_idx:02d}.{fmt}"
            else:
                file_name = f"{base_name}_r{r_idx:02d}_c{c_idx:02d}.{fmt}"

            out_file = output_dir / file_name

            if fmt in ("jpeg", "jpg") and tile_img.mode in ("RGBA", "P"):
                rgb_im = Image.new("RGB", tile_img.size, (255, 255, 255))
                if tile_img.mode == "RGBA":
                    rgb_im.paste(tile_img, mask=tile_img.split()[3])
                else:
                    rgb_im.paste(tile_img.convert("RGB"))
                rgb_im.save(out_file, "JPEG", quality=95)
            else:
                tile_img.save(out_file, format=fmt.upper())

            saved_files.append(out_file)

    return saved_files
