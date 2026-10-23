"""
Lógica pura para divisão e junção de arquivos PDF.
Totalmente desacoplada de interface gráfica e testável via pytest.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf
from pypdf import PdfReader, PdfWriter


def parse_page_ranges(range_str: str, max_pages: int) -> List[List[int]]:
    """
    Converte uma string de intervalos de páginas (ex: "1-3, 5, 7-10") em listas de índices 0-indexed.
    Retorna uma lista de grupos de páginas.
    """
    range_str = range_str.strip()
    if not range_str:
        return [[i for i in range(max_pages)]]

    groups: List[List[int]] = []
    parts = [p.strip() for p in range_str.split(",") if p.strip()]

    for part in parts:
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                start = max(1, int(bounds[0].strip()))
                end = min(max_pages, int(bounds[1].strip()))
                if start <= end:
                    groups.append([i - 1 for i in range(start, end + 1)])
        elif part.isdigit():
            page_num = int(part)
            if 1 <= page_num <= max_pages:
                groups.append([page_num - 1])

    return groups


def get_pdf_info(pdf_path: Path) -> Dict[str, Any]:
    """Retorna informações estruturadas sobre o arquivo PDF."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")

    reader = PdfReader(str(path))
    metadata = reader.metadata or {}

    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "pages": len(reader.pages),
        "is_encrypted": reader.is_encrypted,
        "title": getattr(metadata, "title", None) or str(metadata.get("/Title", "")),
        "author": getattr(metadata, "author", None) or str(metadata.get("/Author", "")),
        "creator": getattr(metadata, "creator", None) or str(metadata.get("/Creator", "")),
    }


def merge_pdfs(
    file_list: List[Path],
    output_path: Path,
    add_bookmarks: bool = True
) -> Path:
    """
    Junta múltiplos arquivos PDF em um único documento ordenado.
    """
    if not file_list:
        raise ValueError("A lista de arquivos PDF para junção está vazia.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    try:
        for file_path in file_list:
            p = Path(file_path)
            if not p.is_file():
                continue
            bookmark = p.stem if add_bookmarks else None
            writer.append(str(p), outline_item=bookmark)

        with open(output_path, "wb") as f_out:
            writer.write(f_out)
    finally:
        writer.close()

    return output_path


def split_pdf(
    src_path: Path,
    output_dir: Path,
    split_mode: str = "all",
    range_str: str = "",
    each_n: int = 1,
    prefix: str = ""
) -> List[Path]:
    """
    Divide um PDF existente em múltiplos arquivos de acordo com o modo escolhido:
    - 'all': uma página por arquivo.
    - 'range': intervalos agrupados (ex: '1-3, 5, 8-10').
    - 'each_n': a cada N páginas por arquivo.
    """
    src_path = Path(src_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("O documento PDF não possui páginas.")

    if not prefix:
        prefix = src_path.stem

    generated_files: List[Path] = []

    if split_mode == "all":
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            out_file = output_dir / f"{prefix}_pag_{i+1:04d}.pdf"
            with open(out_file, "wb") as f:
                writer.write(f)
            generated_files.append(out_file)

    elif split_mode == "range":
        groups = parse_page_ranges(range_str, total_pages)
        if not groups:
            raise ValueError(f"Intervalo de páginas inválido: '{range_str}'")

        for idx, group in enumerate(groups):
            writer = PdfWriter()
            for page_idx in group:
                writer.add_page(reader.pages[page_idx])

            label_start = group[0] + 1
            label_end = group[-1] + 1
            if label_start == label_end:
                out_name = f"{prefix}_pag_{label_start:04d}.pdf"
            else:
                out_name = f"{prefix}_pags_{label_start:04d}-{label_end:04d}.pdf"

            out_file = output_dir / out_name
            with open(out_file, "wb") as f:
                writer.write(f)
            generated_files.append(out_file)

    elif split_mode == "each_n":
        step = max(1, each_n)
        part_idx = 1
        for start_idx in range(0, total_pages, step):
            end_idx = min(start_idx + step, total_pages)
            writer = PdfWriter()
            for p_idx in range(start_idx, end_idx):
                writer.add_page(reader.pages[p_idx])

            out_file = output_dir / f"{prefix}_parte_{part_idx:03d}_pags_{start_idx+1:04d}-{end_idx:04d}.pdf"
            with open(out_file, "wb") as f:
                writer.write(f)
            generated_files.append(out_file)
            part_idx += 1

    else:
        raise ValueError(f"Modo de divisão desconhecido: {split_mode}")

    return generated_files
