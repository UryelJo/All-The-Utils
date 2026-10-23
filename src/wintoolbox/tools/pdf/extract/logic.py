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
