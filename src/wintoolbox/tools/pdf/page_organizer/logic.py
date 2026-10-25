"""
Lógica pura da ferramenta Organizador Visual de Páginas PDF (page_organizer).
Renderiza miniaturas leves via pypdfium2 e compila novos PDFs via pypdf sem dependência de UI.
"""
import io
from pathlib import Path
from typing import Any, Dict, List, Tuple
from pypdf import PdfReader, PdfWriter


def render_page_thumbnails(
    pdf_path: Path,
    scale: float = 0.25,
) -> List[Tuple[int, bytes]]:
    """
    Renderiza miniaturas em memória de todas as páginas do PDF como bytes PNG.
    Retorna lista de tuplas (índice_original_0_based, png_bytes).
    """
    import pypdfium2 as pdfium

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    doc = pdfium.PdfDocument(str(pdf_path))
    thumbnails: List[Tuple[int, bytes]] = []

    try:
        total = len(doc)
        for idx in range(total):
            page = doc[idx]
            try:
                # Renderiza em baixa resolução ideal para miniaturas rápidas
                pil_image = page.render(scale=scale).to_pil()
                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                thumbnails.append((idx, buf.getvalue()))
            finally:
                page.close()
    finally:
        doc.close()

    return thumbnails


def save_organized_pdf(
    src_path: Path,
    dst_path: Path,
    page_plan: List[Dict[str, Any]],
) -> Path:
    """
    Gera um novo arquivo PDF a partir do plano de organização.
    page_plan = [{"original_index": int, "rotation": int (0, 90, 180, 270)}, ...]
    Páginas que não constam no plano são descartadas.
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF de origem não encontrado: {src_path}")

    if not page_plan:
        raise ValueError("O plano de páginas está vazio. Ao menos uma página deve ser mantida.")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    writer = PdfWriter()
    total_src = len(reader.pages)

    for item in page_plan:
        orig_idx = int(item["original_index"])
        rotation = int(item.get("rotation", 0))

        if 0 <= orig_idx < total_src:
            page = reader.pages[orig_idx]
            if rotation != 0:
                page.rotate(rotation)
            writer.add_page(page)

    with open(dst_path, "wb") as f_out:
        writer.write(f_out)

    return dst_path
