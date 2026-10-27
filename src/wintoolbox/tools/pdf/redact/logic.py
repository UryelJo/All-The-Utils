"""
Lógica pura de censura e tarjamento permanente de texto e áreas sensíveis em documentos PDF.
Localiza palavras-chave via extração de layout e aplica retângulos opacos permanentes.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import io
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import pdfplumber
import pypdf
from reportlab.lib.colors import black, white
from reportlab.pdfgen import canvas


def redact_terms_and_regions(
    pdf_path: Path,
    output_pdf_path: Path,
    terms: List[str],
    custom_rects: Optional[List[Dict[str, Any]]] = None,
    case_sensitive: bool = False,
    fill_color_black: bool = True,
) -> Dict[str, Any]:
    """
    Localiza palavras-chave no PDF e aplica tarjas retangulares opacas permanentes.
    custom_rects: lista de dicionários {'page': int (1-indexed), 'x': float, 'y': float, 'w': float, 'h': float}
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    terms_to_search = [t.strip() for t in terms if t.strip()]
    if not terms_to_search and not custom_rects:
        raise ValueError("Nenhum termo ou retângulo informado para censura.")

    # Mapeia retângulos a serem tarjados por página (1-indexed)
    redaction_map: Dict[int, List[Dict[str, float]]] = {}
    found_occurrences_count = 0

    # 1. Varre palavras-chave via pdfplumber
    with pdfplumber.open(pdf_path) as plum_pdf:
        for page_idx, page in enumerate(plum_pdf.pages):
            page_num = page_idx + 1
            page_h = float(page.height)
            words = page.extract_words()

            for term in terms_to_search:
                pattern = re.compile(
                    re.escape(term),
                    0 if case_sensitive else re.IGNORECASE,
                )

                for w in words:
                    text = w.get("text", "")
                    if pattern.search(text):
                        x0 = float(w["x0"])
                        top = float(w["top"])
                        x1 = float(w["x1"])
                        bottom = float(w["bottom"])

                        # Converte de coordenadas de topo para coordenadas de base (PDF padrão)
                        w_pt = x1 - x0
                        h_pt = bottom - top
                        y_pdf = page_h - bottom

                        redaction_map.setdefault(page_num, []).append({
                            "x": x0 - 2.0,  # Pequena folga visual
                            "y": y_pdf - 2.0,
                            "w": w_pt + 4.0,
                            "h": h_pt + 4.0,
                        })
                        found_occurrences_count += 1

    # 2. Adiciona retângulos manuais se fornecidos
    if custom_rects:
        for cr in custom_rects:
            p_num = cr.get("page", 1)
            redaction_map.setdefault(p_num, []).append({
                "x": float(cr.get("x", 0)),
                "y": float(cr.get("y", 0)),
                "w": float(cr.get("w", 50)),
                "h": float(cr.get("h", 20)),
            })

    # 3. Gera e aplica overlays de tarja opaca via pypdf e ReportLab
    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        page_box = page.mediabox
        pw = float(page_box.width)
        ph = float(page_box.height)

        rects = redaction_map.get(page_num, [])
        if rects:
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(pw, ph))

            if fill_color_black:
                can.setFillColor(black)
            else:
                can.setFillColor(white)

            for r in rects:
                can.rect(r["x"], r["y"], r["w"], r["h"], fill=1, stroke=0)

            can.save()
            packet.seek(0)
            overlay = pypdf.PdfReader(packet).pages[0]
            page.merge_page(overlay)

        writer.add_page(page)

    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

    return {
        "status": "CONCLUIDO",
        "output_path": str(output_pdf_path),
        "total_redactions": found_occurrences_count + (len(custom_rects) if custom_rects else 0),
        "pages_affected": len(redaction_map),
    }
