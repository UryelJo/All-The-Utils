"""
Lógica pura para leitura e edição completa de metadados e marcadores de sumário (TOC Bookmarks/Outlines) em PDFs.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf


def extract_metadata_and_bookmarks(pdf_path: Path) -> Dict[str, Any]:
    """
    Extrai metadados padrão e árvore de marcadores (TOC) do documento PDF.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    reader = pypdf.PdfReader(pdf_path)
    meta = reader.metadata or {}

    metadata_dict = {
        "title": str(meta.get("/Title") or ""),
        "author": str(meta.get("/Author") or ""),
        "subject": str(meta.get("/Subject") or ""),
        "keywords": str(meta.get("/Keywords") or ""),
        "creator": str(meta.get("/Creator") or ""),
        "producer": str(meta.get("/Producer") or ""),
    }

    bookmarks_list: List[Dict[str, Any]] = []

    def parse_outline(items):
        for item in items:
            if isinstance(item, list):
                parse_outline(item)
            elif isinstance(item, pypdf.generic.Destination):
                try:
                    p_num = reader.get_destination_page_number(item) + 1
                except Exception:
                    p_num = 1
                bookmarks_list.append({
                    "title": str(item.title),
                    "page": p_num,
                })

    try:
        if reader.outline:
            parse_outline(reader.outline)
    except Exception:
        pass

    return {
        "total_pages": len(reader.pages),
        "metadata": metadata_dict,
        "bookmarks": bookmarks_list,
    }


def save_metadata_and_bookmarks(
    pdf_path: Path,
    output_pdf_path: Path,
    metadata: Dict[str, str],
    bookmarks: List[Dict[str, Any]],
) -> Path:
    """
    Grava os novos metadados e reconstrói os marcadores (bookmarks) do PDF.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter(clone_from=reader)

    # 1. Atualiza metadados
    pdf_meta = {
        "/Title": metadata.get("title", ""),
        "/Author": metadata.get("author", ""),
        "/Subject": metadata.get("subject", ""),
        "/Keywords": metadata.get("keywords", ""),
    }
    writer.add_metadata(pdf_meta)

    # 2. Adiciona bookmarks
    total_pages = len(writer.pages)
    for b in bookmarks:
        title = b.get("title", "").strip()
        p_num = int(b.get("page", 1))
        # Converte para 0-indexed
        page_idx = max(0, min(total_pages - 1, p_num - 1))
        if title:
            writer.add_outline_item(title=title, page_number=page_idx)

    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

    return output_pdf_path
