"""
Lógica pura para extração de texto estruturado e imagens embutidas de PDFs.
"""
import io
from pathlib import Path
from typing import List
from PIL import Image
from pypdf import PdfReader


def extract_text_from_pdf(
    pdf_path: Path,
    include_page_headers: bool = True
) -> str:
    """
    Extrai todo o texto legível do arquivo PDF página a página.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    chunks: List[str] = []

    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if include_page_headers:
            chunks.append(f"--- Página {idx + 1} ---\n{page_text.strip()}")
        else:
            chunks.append(page_text.strip())

    return "\n\n".join(chunks)


def extract_images_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    min_dimension: int = 40,
    prefix: str = "extraida"
) -> List[Path]:
    """
    Extrai todas as imagens embutidas nas páginas do PDF com filtro de dimensão mínima.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path))
    extracted_paths: List[Path] = []
    img_counter = 1

    for page_idx, page in enumerate(reader.pages):
        for img_file in page.images:
            try:
                raw_bytes = img_file.data
                with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                    w, h = pil_img.size
                    if w < min_dimension or h < min_dimension:
                        continue

                    # Determina extensão ideal
                    fmt = pil_img.format or "PNG"
                    ext = ".jpg" if fmt.upper() in ("JPEG", "JPG") else ".png"

                    out_name = f"{prefix}_pag_{page_idx + 1:04d}_{img_counter:03d}{ext}"
                    out_path = output_dir / out_name

                    if ext == ".png" and pil_img.mode not in ("RGB", "RGBA"):
                        pil_img.convert("RGBA").save(out_path, format="PNG")
                    else:
                        pil_img.save(out_path)

                    extracted_paths.append(out_path)
                    img_counter += 1
            except Exception:
                continue

    return extracted_paths


def parse_page_selection(selection: str, page_count: int) -> List[int]:
    """'1-3, 5, 8-' -> índices 0-based válidos; vazio = todas as páginas."""
    selection = (selection or "").replace(" ", "")
    if not selection:
        return list(range(page_count))
    pages: List[int] = []
    for part in selection.split(","):
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s) if start_s else 1
            end = int(end_s) if end_s else page_count
        else:
            start = end = int(part)
        for n in range(max(1, start), min(page_count, end) + 1):
            if n - 1 not in pages:
                pages.append(n - 1)
    if not pages:
        raise ValueError(f"Nenhuma página válida em '{selection}' (o PDF tem {page_count} páginas).")
    return pages


def render_pdf_pages(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 150,
    img_format: str = "png",
    selection: str = "",
    quality: int = 90,
    progress_cb=None,
) -> List[Path]:
    """
    Renderiza páginas do PDF como imagens (PNG/JPG/WEBP) via pypdfium2 (motor PDFium do Chrome).
    """
    import pypdfium2 as pdfium

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt = img_format.lower().lstrip(".")
    if fmt == "jpeg":
        fmt = "jpg"
    save_fmt = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}.get(fmt)
    if not save_fmt:
        raise ValueError(f"Formato de imagem não suportado: {img_format}")

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        indices = parse_page_selection(selection, len(pdf))
        digits = len(str(len(pdf)))
        outputs: List[Path] = []
        for i, idx in enumerate(indices):
            page = pdf[idx]
            try:
                image = page.render(scale=dpi / 72).to_pil()
            finally:
                page.close()
            if save_fmt == "JPEG" and image.mode != "RGB":
                image = image.convert("RGB")
            number = str(idx + 1).zfill(digits)
            out = output_dir / f"{pdf_path.stem}_pagina_{number}.{fmt}"
            if save_fmt == "PNG":
                image.save(out, format=save_fmt, dpi=(dpi, dpi), optimize=True)
            else:
                image.save(out, format=save_fmt, dpi=(dpi, dpi), quality=quality)
            outputs.append(out)
            if progress_cb:
                progress_cb(i + 1, len(indices), out.name)
        return outputs
    finally:
        pdf.close()
