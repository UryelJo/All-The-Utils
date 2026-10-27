"""
Lógica pura para higienização e melhoria de digitalizações e scans de documentos PDF.
Realce de contraste, nitidez, conversão para preto e branco puro e eliminação de ruídos.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from PIL import Image, ImageEnhance, ImageFilter
import pypdfium2


def cleanup_scanned_pdf(
    input_pdf_path: Path,
    output_pdf_path: Path,
    contrast_factor: float = 1.8,
    to_pure_bw: bool = True,
    binarize_threshold: int = 180,
    sharpen: bool = True,
    dpi: int = 150,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Renderiza cada página do PDF, aplica filtros de contraste e binarização de digitalização,
    e reconstrói o PDF higienizado de alta legibilidade.
    """
    input_pdf_path = Path(input_pdf_path).resolve()
    if not input_pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {input_pdf_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = pypdfium2.PdfDocument(str(input_pdf_path))
    total_pages = len(pdf)
    if total_pages == 0:
        raise ValueError("O documento PDF não possui páginas.")

    processed_images: List[Image.Image] = []
    scale = dpi / 72.0

    for idx, page in enumerate(pdf):
        pil_img = page.render(scale=scale).to_pil()

        # 1. Realce de Contraste
        if contrast_factor != 1.0:
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(contrast_factor)

        # 2. Nitidez
        if sharpen:
            pil_img = pil_img.filter(ImageFilter.SHARPEN)

        # 3. Binarização / Conversão para Preto e Branco Puro
        if to_pure_bw:
            gray = pil_img.convert("L")
            # Pixels mais claros que o threshold viram 255 (branco), demais viram 0 (preto)
            bw_img = gray.point(lambda p: 255 if p > binarize_threshold else 0, mode="1")
            processed_images.append(bw_img.convert("RGB"))
        else:
            processed_images.append(pil_img.convert("L").convert("RGB"))

        if progress_cb and total_pages > 0:
            progress_cb(int(((idx + 1) / total_pages) * 100))

    if not processed_images:
        raise RuntimeError("Nenhuma página pôde ser processada.")

    first_page = processed_images[0]
    rest = processed_images[1:] if len(processed_images) > 1 else []

    first_page.save(
        output_pdf_path,
        save_all=True,
        append_images=rest,
        format="PDF",
        resolution=dpi,
    )

    return output_pdf_path
