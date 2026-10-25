"""
Lógica pura da ferramenta Numeração, Carimbos e Marca d'Água em PDF (pdf.stamp).
Aplica numerações de páginas e carimbos textuais via reportlab e pypdf sem acoplamento com interface gráfica.
"""
import io
from pathlib import Path
from typing import Optional, Set
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen import canvas

from wintoolbox.tools.pdf.split_merge.logic import parse_page_ranges


def get_target_pages_set(range_str: str, total_pages: int) -> Set[int]:
    """Retorna conjunto de índices de página (0-based) a partir da string de intervalo."""
    if not range_str or not range_str.strip():
        return set(range(total_pages))
    try:
        groups = parse_page_ranges(range_str, total_pages)
        pages: Set[int] = set()
        for g in groups:
            for p in g:
                if 0 <= p < total_pages:
                    pages.add(p)
        return pages if pages else set(range(total_pages))
    except Exception:
        return set(range(total_pages))


def format_numbering_text(template: str, current_page: int, total_pages: int) -> str:
    """Substitui marcadores com segurança sem lançar exceções para chaves desconhecidas."""
    return (
        template.replace("{page}", str(current_page))
        .replace("{total}", str(total_pages))
        .replace("{n}", str(current_page))
    )


def apply_stamp_and_numbering(
    src_path: Path,
    dst_path: Path,
    # Configuração de Numeração
    enable_numbering: bool = True,
    numbering_format: str = "Página {page} de {total}",
    numbering_position: str = "bottom_center",
    numbering_font_size: int = 10,
    numbering_color_hex: str = "#666666",
    # Configuração de Carimbo / Marca d'Água
    enable_watermark: bool = False,
    watermark_text: str = "CONFIDENCIAL",
    watermark_rotation: int = 45,
    watermark_opacity: float = 0.25,
    watermark_font_size: int = 50,
    watermark_color_hex: str = "#d83b01",
    # Filtro de páginas
    page_range_str: str = "",
) -> Path:
    """
    Aplica numeração de páginas e/ou carimbo/marca d'água no PDF.
    Compatível com pypdf 6+ sem DeprecationWarnings e com tratamento de orientação de páginas.
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {src_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    writer = PdfWriter()
    total_pages = len(reader.pages)
    target_pages = get_target_pages_set(page_range_str, total_pages)

    num_color = HexColor(numbering_color_hex)
    wm_color_raw = HexColor(watermark_color_hex)
    wm_color = Color(wm_color_raw.red, wm_color_raw.green, wm_color_raw.blue, alpha=watermark_opacity)

    for idx, page in enumerate(reader.pages):
        if idx not in target_pages:
            writer.add_page(page)
            continue

        # Normaliza rotações da página para coordenadas consistentes
        try:
            page.transfer_rotation_to_content()
        except Exception:
            pass

        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))

        # 1. Carimbo / Marca d'água (fundo)
        if enable_watermark and watermark_text.strip():
            can.saveState()
            can.setFont("Helvetica-Bold", watermark_font_size)
            can.setFillColor(wm_color)
            can.translate(width / 2, height / 2)
            can.rotate(watermark_rotation)
            can.drawCentredString(0, 0, watermark_text.strip())
            can.restoreState()

        # 2. Numeração de páginas
        if enable_numbering:
            can.saveState()
            can.setFont("Helvetica", numbering_font_size)
            can.setFillColor(num_color)

            num_str = format_numbering_text(numbering_format, idx + 1, total_pages)

            if numbering_position == "bottom_center":
                can.drawCentredString(width / 2, 24, num_str)
            elif numbering_position == "bottom_right":
                can.drawRightString(width - 36, 24, num_str)
            elif numbering_position == "top_right":
                can.drawRightString(width - 36, height - 28, num_str)
            elif numbering_position == "top_center":
                can.drawCentredString(width / 2, height - 28, num_str)
            else:
                can.drawCentredString(width / 2, 24, num_str)

            can.restoreState()

        can.save()
        packet.seek(0)

        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]

        # Anexa ao writer ANTES de merge_page para conformidade com pypdf 6 e 7
        added_page = writer.add_page(page)
        added_page.merge_page(overlay_page)

    with open(dst_path, "wb") as f_out:
        writer.write(f_out)

    return dst_path
