"""
Lógica pura de imposição de páginas para impressão (N-Up e Livreto/Booklet).
Agrupa múltiplas páginas por folha (2-Up, 4-Up) e reorganiza a ordem de páginas para encadernação.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import pypdf
from pypdf import Transformation


def calculate_booklet_order(total_pages: int) -> List[Optional[int]]:
    """
    Calcula a sequência correta de páginas para impressão de livreto frente e verso (dobra ao meio).
    Retorna números de página 1-indexados ou None para páginas em branco de preenchimento.
    """
    if total_pages <= 0:
        return []

    # O número total de páginas em um livreto deve ser múltiplo de 4
    slots = ((total_pages + 3) // 4) * 4
    pages_seq: List[Optional[int]] = []

    left = slots
    right = 1

    while right < left:
        # Folha Frente: [Página Externa Esquerda, Página Externa Direita]
        p_left = left if left <= total_pages else None
        p_right = right if right <= total_pages else None
        pages_seq.extend([p_left, p_right])

        left -= 1
        right += 1

        # Folha Verso: [Página Interna Esquerda, Página Interna Direita]
        p_left_v = right if right <= total_pages else None
        p_right_v = left if left <= total_pages else None
        pages_seq.extend([p_left_v, p_right_v])

        left -= 1
        right += 1

    return pages_seq


def process_nup_or_booklet(
    input_pdf_path: Path,
    output_pdf_path: Path,
    mode: str = "2UP",  # "2UP", "4UP", "BOOKLET"
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Aplica a transformação N-Up ou imposição de livreto sobre o documento PDF.
    """
    input_pdf_path = Path(input_pdf_path).resolve()
    if not input_pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {input_pdf_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(input_pdf_path)
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("O arquivo PDF está vazio.")

    writer = pypdf.PdfWriter()

    # Dimensões A4 padrão em pontos
    a4_w = 595.27
    a4_h = 841.89

    if mode == "BOOKLET":
        # Livreto: reordena as páginas em pares 2-up em folha A4 paisagem
        booklet_seq = calculate_booklet_order(total_pages)
        total_sheets = len(booklet_seq) // 2

        for sheet_idx in range(total_sheets):
            p1_idx = booklet_seq[sheet_idx * 2]
            p2_idx = booklet_seq[sheet_idx * 2 + 1]

            # Folha A4 Paisagem
            sheet_page = writer.add_blank_page(width=a4_h, height=a4_w)

            # Sub-página esquerda
            if p1_idx is not None:
                src_p1 = reader.pages[p1_idx - 1]
                w1 = float(src_p1.mediabox.width)
                h1 = float(src_p1.mediabox.height)
                scale = min((a4_h / 2) / w1, a4_w / h1) * 0.95
                tx = ((a4_h / 2) - (w1 * scale)) / 2
                ty = (a4_w - (h1 * scale)) / 2
                sheet_page.merge_transformed_page(
                    src_p1,
                    Transformation().scale(scale, scale).translate(tx, ty),
                )

            # Sub-página direita
            if p2_idx is not None:
                src_p2 = reader.pages[p2_idx - 1]
                w2 = float(src_p2.mediabox.width)
                h2 = float(src_p2.mediabox.height)
                scale = min((a4_h / 2) / w2, a4_w / h2) * 0.95
                tx = (a4_h / 2) + ((a4_h / 2) - (w2 * scale)) / 2
                ty = (a4_w - (h2 * scale)) / 2
                sheet_page.merge_transformed_page(
                    src_p2,
                    Transformation().scale(scale, scale).translate(tx, ty),
                )

            if progress_cb and total_sheets > 0:
                progress_cb(int(((sheet_idx + 1) / total_sheets) * 100))

    elif mode == "2UP":
        # 2 páginas por folha em A4 paisagem
        total_sheets = (total_pages + 1) // 2

        for sheet_idx in range(total_sheets):
            idx1 = sheet_idx * 2
            idx2 = sheet_idx * 2 + 1

            sheet_page = writer.add_blank_page(width=a4_h, height=a4_w)

            # Página esquerda
            src_p1 = reader.pages[idx1]
            w1 = float(src_p1.mediabox.width)
            h1 = float(src_p1.mediabox.height)
            scale1 = min((a4_h / 2) / w1, a4_w / h1) * 0.95
            tx1 = ((a4_h / 2) - (w1 * scale1)) / 2
            ty1 = (a4_w - (h1 * scale1)) / 2
            sheet_page.merge_transformed_page(
                src_p1,
                Transformation().scale(scale1, scale1).translate(tx1, ty1),
            )

            # Página direita (se houver)
            if idx2 < total_pages:
                src_p2 = reader.pages[idx2]
                w2 = float(src_p2.mediabox.width)
                h2 = float(src_p2.mediabox.height)
                scale2 = min((a4_h / 2) / w2, a4_w / h2) * 0.95
                tx2 = (a4_h / 2) + ((a4_h / 2) - (w2 * scale2)) / 2
                ty2 = (a4_w - (h2 * scale2)) / 2
                sheet_page.merge_transformed_page(
                    src_p2,
                    Transformation().scale(scale2, scale2).translate(tx2, ty2),
                )

            if progress_cb and total_sheets > 0:
                progress_cb(int(((sheet_idx + 1) / total_sheets) * 100))

    elif mode == "4UP":
        # 4 páginas por folha em grade 2x2 em A4 retrato
        total_sheets = (total_pages + 3) // 4
        half_w = a4_w / 2
        half_h = a4_h / 2

        for sheet_idx in range(total_sheets):
            sheet_page = writer.add_blank_page(width=a4_w, height=a4_h)

            positions = [
                (0, half_h),        # Superior Esquerdo
                (half_w, half_h),   # Superior Direito
                (0, 0),             # Inferior Esquerdo
                (half_w, 0),        # Inferior Direito
            ]

            for slot_idx, (base_x, base_y) in enumerate(positions):
                p_idx = sheet_idx * 4 + slot_idx
                if p_idx < total_pages:
                    src_p = reader.pages[p_idx]
                    pw = float(src_p.mediabox.width)
                    ph = float(src_p.mediabox.height)
                    scale = min(half_w / pw, half_h / ph) * 0.95
                    tx = base_x + (half_w - (pw * scale)) / 2
                    ty = base_y + (half_h - (ph * scale)) / 2
                    sheet_page.merge_transformed_page(
                        src_p,
                        Transformation().scale(scale, scale).translate(tx, ty),
                    )

            if progress_cb and total_sheets > 0:
                progress_cb(int(((sheet_idx + 1) / total_sheets) * 100))

    else:
        raise ValueError(f"Modo não suportado: {mode}")

    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

    return output_pdf_path
