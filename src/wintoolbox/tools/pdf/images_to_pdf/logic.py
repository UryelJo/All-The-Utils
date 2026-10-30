"""
Lógica pura para conversão de imagens em lote para documento PDF.
Compatível com Pillow, pillow-heif (iPhone HEIC/HEIF) e pypdf, sem necessidade de dependências pesadas.
"""
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageOps

from wintoolbox.tools.images.convert.logic import _apply_color_profile, ensure_heif_registered

ensure_heif_registered()

PAGE_SIZES: Dict[str, Tuple[int, int]] = {
    "A4": (595, 842),       # 210 x 297 mm em 72 DPI
    "Carta (Letter)": (612, 792),  # 8.5 x 11 pol
    "Ofício (Legal)": (612, 1008),  # 8.5 x 14 pol
    "Original da Imagem": (0, 0),
}


def convert_images_to_pdf(
    image_paths: List[Path],
    output_path: Path,
    page_size_name: str = "A4",
    orientation: str = "auto",
    margin_pt: int = 20,
    fit_mode: str = "fit"
) -> Path:
    """
    Converte uma lista ordenada de caminhos de imagens em um documento PDF consolidado.
    Suporta fotos HEIC/HEIF de iPhone com transposição automática EXIF e conversão Display P3 -> sRGB.
    """
    ensure_heif_registered()

    if not image_paths:
        raise ValueError("A lista de imagens para conversão está vazia.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_size = PAGE_SIZES.get(page_size_name, (595, 842))
    pdf_pages: List[Image.Image] = []

    try:
        for img_p in image_paths:
            p = Path(img_p)
            if not p.is_file():
                continue

            with Image.open(p) as img_opened:
                raw_icc = img_opened.info.get("icc_profile")
                img_transposed = ImageOps.exif_transpose(img_opened)
                img_raw, _ = _apply_color_profile(
                    img_transposed,
                    raw_icc,
                    color_profile_mode="srgb",
                    target_supports_icc=False,
                )
                # Normaliza modo de cor para RGB (converte RGBA / P / 1 para RGB com fundo branco)
                if img_raw.mode in ("RGBA", "LA") or (img_raw.mode == "P" and "transparency" in img_raw.info):
                    bg = Image.new("RGB", img_raw.size, (255, 255, 255))
                    alpha = img_raw.convert("RGBA").split()[3]
                    bg.paste(img_raw.convert("RGB"), mask=alpha)
                    img = bg
                else:
                    img = img_raw.convert("RGB")

                img_w, img_h = img.size

                if base_size == (0, 0):
                    # Tamanho original
                    pdf_pages.append(img.copy())
                    continue

                target_w, target_h = base_size

                # Orientação
                if orientation == "auto":
                    if img_w > img_h and target_h > target_w:
                        target_w, target_h = target_h, target_w
                    elif img_h > img_w and target_w > target_h:
                        target_w, target_h = target_h, target_w
                elif orientation == "landscape":
                    if target_h > target_w:
                        target_w, target_h = target_h, target_w
                elif orientation == "portrait":
                    if target_w > target_h:
                        target_w, target_h = target_h, target_w

                # Resolução de renderização em DPI apropriado (150 ou proporção com pontos)
                # Escala pontos para pixels em 150 DPI (fator ~2.08)
                scale_dpi = 150 / 72.0
                canvas_w = int(target_w * scale_dpi)
                canvas_h = int(target_h * scale_dpi)
                margin_px = int(margin_pt * scale_dpi)

                usable_w = max(1, canvas_w - (2 * margin_px))
                usable_h = max(1, canvas_h - (2 * margin_px))

                # Redimensiona imagem respeitando proporções
                ratio = min(usable_w / img_w, usable_h / img_h)
                new_w = max(1, int(img_w * ratio))
                new_h = max(1, int(img_h * ratio))

                resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Cria canvas de página em branco e centraliza
                page_canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
                pos_x = (canvas_w - new_w) // 2
                pos_y = (canvas_h - new_h) // 2
                page_canvas.paste(resized_img, (pos_x, pos_y))

                pdf_pages.append(page_canvas)

        if not pdf_pages:
            raise ValueError("Nenhuma imagem válida pôde ser processada.")

        # Grava como PDF em uma única chamada do Pillow
        first_page = pdf_pages[0]
        other_pages = pdf_pages[1:] if len(pdf_pages) > 1 else []

        first_page.save(
            output_path,
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=other_pages
        )

    finally:
        for page in pdf_pages:
            try:
                page.close()
            except Exception:
                pass

    return output_path
