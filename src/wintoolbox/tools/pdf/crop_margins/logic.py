"""
Lógica pura para corte e ajuste de margens em documentos PDF (automático por conteúdo ou manual).

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import pdfplumber
import pypdf


def crop_pdf_document(
    input_pdf_path: Path,
    output_pdf_path: Path,
    auto_crop: bool = True,
    padding_pt: float = 10.0,
    margin_left_pt: float = 0.0,
    margin_bottom_pt: float = 0.0,
    margin_right_pt: float = 0.0,
    margin_top_pt: float = 0.0,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Ajusta a CropBox de todas as páginas do PDF eliminando margens vazias.
    """
    input_pdf_path = Path(input_pdf_path).resolve()
    if not input_pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {input_pdf_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(input_pdf_path)
    writer = pypdf.PdfWriter(clone_from=reader)
    total_pages = len(writer.pages)

    if total_pages == 0:
        raise ValueError("O documento PDF está vazio.")

    # Se for automático, calcula o bounding box por página via pdfplumber
    auto_boxes: Dict[int, tuple] = {}
    if auto_crop:
        with pdfplumber.open(input_pdf_path) as plum:
            for p_idx, page in enumerate(plum.pages):
                words = page.extract_words()
                if words:
                    min_x0 = min(float(w["x0"]) for w in words)
                    min_top = min(float(w["top"]) for w in words)
                    max_x1 = max(float(w["x1"]) for w in words)
                    max_bottom = max(float(w["bottom"]) for w in words)

                    ph = float(page.height)
                    pw = float(page.width)

                    # Converte de topo para base
                    y_lower = ph - max_bottom - padding_pt
                    y_upper = ph - min_top + padding_pt
                    x_lower = min_x0 - padding_pt
                    x_upper = max_x1 + padding_pt

                    # Garante limites válidos dentro da folha
                    x_lower = max(0.0, x_lower)
                    y_lower = max(0.0, y_lower)
                    x_upper = min(pw, x_upper)
                    y_upper = min(ph, y_upper)

                    if x_upper > x_lower and y_upper > y_lower:
                        auto_boxes[p_idx] = (x_lower, y_lower, x_upper, y_upper)

    for idx, page in enumerate(writer.pages):
        box = page.mediabox
        x0 = float(box.left)
        y0 = float(box.bottom)
        x1 = float(box.right)
        y1 = float(box.top)

        if auto_crop and idx in auto_boxes:
            bx0, by0, bx1, by1 = auto_boxes[idx]
            page.cropbox.lower_left = (bx0, by0)
            page.cropbox.upper_right = (bx1, by1)
        elif not auto_crop:
            new_x0 = x0 + margin_left_pt
            new_y0 = y0 + margin_bottom_pt
            new_x1 = x1 - margin_right_pt
            new_y1 = y1 - margin_top_pt
            if new_x1 > new_x0 and new_y1 > new_y0:
                page.cropbox.lower_left = (new_x0, new_y0)
                page.cropbox.upper_right = (new_x1, new_y1)

        if progress_cb and total_pages > 0:
            progress_cb(int(((idx + 1) / total_pages) * 100))

    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

    return output_pdf_path
