"""
Lógica pura para rotação de páginas de arquivos PDF.
"""
from pathlib import Path
from typing import List, Set
from pypdf import PdfReader, PdfWriter

from wintoolbox.tools.pdf.split_merge.logic import parse_page_ranges


def rotate_pdf(
    src_path: Path,
    dst_path: Path,
    angle: int = 90,
    pages_mode: str = "all",
    range_str: str = ""
) -> Path:
    """
    Rotaciona páginas de um PDF no sentido horário pelo ângulo especificado (90, 180, 270).
    """
    src_path = Path(src_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    writer = PdfWriter()
    total_pages = len(reader.pages)

    target_indices: Set[int] = set()

    if pages_mode == "all":
        target_indices = set(range(total_pages))
    elif pages_mode == "odd":  # 1-indexed odd: 1, 3, 5 -> 0, 2, 4
        target_indices = {i for i in range(total_pages) if (i + 1) % 2 != 0}
    elif pages_mode == "even": # 1-indexed even: 2, 4, 6 -> 1, 3, 5
        target_indices = {i for i in range(total_pages) if (i + 1) % 2 == 0}
    elif pages_mode == "range":
        groups = parse_page_ranges(range_str, total_pages)
        for g in groups:
            target_indices.update(g)
    else:
        target_indices = set(range(total_pages))

    for idx, page in enumerate(reader.pages):
        if idx in target_indices:
            page.rotate(angle)
        writer.add_page(page)

    with open(dst_path, "wb") as f_out:
        writer.write(f_out)

    return dst_path
