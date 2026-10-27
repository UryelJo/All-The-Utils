"""
Lógica pura para inserção visual de assinatura digitalizada (PNG com transparência)
e carimbo de data sobre páginas de documentos PDF.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas


def apply_visual_signature(
    pdf_path: Path,
    signature_img_path: Path,
    output_pdf_path: Path,
    page_number: int = 1,  # 1-indexed; -1 para aplicar em todas as páginas
    x_pt: float = 100.0,
    y_pt: float = 100.0,
    width_pt: float = 150.0,
    height_pt: float = 50.0,
    add_date: bool = False,
    date_text: Optional[str] = None,
) -> Path:
    """
    Aplica a assinatura visual e dados opcionais sobre o PDF especificado.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    signature_img_path = Path(signature_img_path).resolve()
    if not signature_img_path.is_file():
        raise FileNotFoundError(f"Arquivo de imagem da assinatura não encontrado: {signature_img_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("O documento PDF não possui páginas.")

    # Gera o overlay com a assinatura usando ReportLab em memória
    def create_signature_overlay(page_w: float, page_h: float) -> pypdf.PageObject:
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_w, page_h))

        # Desenha a imagem da assinatura
        can.drawImage(
            str(signature_img_path),
            x_pt,
            y_pt,
            width=width_pt,
            height=height_pt,
            mask="auto",
            preserveAspectRatio=True,
        )

        if add_date and date_text:
            can.setFont("Helvetica", 9)
            can.setFillColor(black)
            can.drawString(x_pt, max(0.0, y_pt - 12.0), date_text)

        can.save()
        packet.seek(0)
        overlay_reader = pypdf.PdfReader(packet)
        return overlay_reader.pages[0]

    for idx, page in enumerate(reader.pages):
        current_page_num = idx + 1
        page_box = page.mediabox
        page_w = float(page_box.width)
        page_h = float(page_box.height)

        if page_number == -1 or current_page_num == page_number:
            overlay_page = create_signature_overlay(page_w, page_h)
            page.merge_page(overlay_page)

        writer.add_page(page)

    with open(output_pdf_path, "wb") as out_f:
        writer.write(out_f)

    return output_pdf_path
