"""
Lógica pura para extração de texto de regiões da tela (Text Extractor).

Recorta regiões capturadas e invoca os motores locais de OCR do sistema.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.tools.images.ocr.logic import perform_ocr_on_image

_log = get_logger("images.text_extractor.logic")


def clean_extracted_text(raw_text: str) -> str:
    """Higieniza o texto extraído, normalizando quebras de linha e espaços duplos."""
    if not raw_text:
        return ""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_text_from_image_region(
    image: Image.Image,
    crop_box: Optional[Tuple[int, int, int, int]] = None,
    temp_dir: Optional[Path] = None
) -> str:
    """
    Recorta uma região de imagem em memória e extrai seu texto via OCR local.

    Args:
        image: Imagem base PIL (captura de tela ou arquivo).
        crop_box: Tupla (x1, y1, x2, y2) da região selecionada, ou None para imagem completa.
        temp_dir: Diretório opcional para armazenar o arquivo temporário.

    Returns:
        Texto reconhecido limpo.
    """
    if crop_box:
        x1, y1, x2, y2 = crop_box
        left = max(0, min(x1, x2))
        top = max(0, min(y1, y2))
        right = min(image.width, max(x1, x2))
        bottom = min(image.height, max(y1, y2))

        if right <= left or bottom <= top:
            return ""

        target_img = image.crop((left, top, right, bottom))
    else:
        target_img = image

    with tempfile.NamedTemporaryFile(suffix=".png", dir=temp_dir, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Salva em PNG para alimentar o motor OCR WinRT / Tesseract
        target_img.save(tmp_path, format="PNG")
        raw_text = perform_ocr_on_image(tmp_path)
        return clean_extracted_text(raw_text)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
