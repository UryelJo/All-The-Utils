"""
Lógica pura para recorte visual e rotação fina de imagens.

Processa corte com proporções geométricas exatas e rotações angulares
utilizando Pillow, totalmente desacoplado da interface gráfica.
"""
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("images.crop_editor.logic")

# Proporções pré-definidas (Largura:Altura)
ASPECT_RATIOS = {
    "Livre": None,
    "1:1 (Quadrado)": (1, 1),
    "16:9 (Paisagem / YouTube)": (16, 9),
    "9:16 (Story / Reels / Shorts)": (9, 16),
    "4:5 (Instagram Retrato)": (4, 5),
    "4:3 (Fotografia Padrão)": (4, 3),
    "3:2 (Sensor DSLR)": (3, 2),
    "A4 (Proporção Documento)": (1, 1.4142),
}


def calculate_aspect_box(
    img_width: int,
    img_height: int,
    aspect_ratio: Optional[Tuple[float, float]],
    margin_ratio: float = 0.9
) -> Tuple[int, int, int, int]:
    """
    Calcula uma caixa inicial centralizada para a proporção informada.

    Args:
        img_width: Largura da imagem original.
        img_height: Altura da imagem original.
        aspect_ratio: Tupla (largura, altura) da proporção, ou None para livre.
        margin_ratio: Fração da área útil ocupada pela caixa inicial (default 90%).

    Returns:
        Tupla (x1, y1, x2, y2) com coordenadas inteiras válidas.
    """
    if img_width <= 0 or img_height <= 0:
        raise ValueError("Dimensões da imagem devem ser positivas.")

    if not aspect_ratio:
        # Modo livre: ocupa a maior parte da imagem com margem
        w = int(img_width * margin_ratio)
        h = int(img_height * margin_ratio)
        x1 = (img_width - w) // 2
        y1 = (img_height - h) // 2
        return (x1, y1, x1 + w, y1 + h)

    ar_w, ar_h = aspect_ratio
    target_ratio = ar_w / ar_h

    # Tenta ajustar pela largura
    box_w = int(img_width * margin_ratio)
    box_h = int(box_w / target_ratio)

    # Se a altura ultrapassar, ajusta pela altura
    if box_h > int(img_height * margin_ratio):
        box_h = int(img_height * margin_ratio)
        box_w = int(box_h * target_ratio)

    x1 = (img_width - box_w) // 2
    y1 = (img_height - box_h) // 2
    return (x1, y1, x1 + box_w, y1 + box_h)


def apply_crop_and_rotation(
    image: Image.Image,
    crop_box: Tuple[int, int, int, int],
    rotation_angle: float = 0.0
) -> Image.Image:
    """
    Aplica rotação fina e recorte na imagem.

    A rotação é aplicada primeiro usando interpolação bicúbica de alta qualidade,
    seguida pelo recorte nas coordenadas especificadas.

    Args:
        image: Instância PIL Image.
        crop_box: Tupla (x1, y1, x2, y2).
        rotation_angle: Ângulo em graus (-45° a +45° ou qualquer valor).

    Returns:
        Nova imagem recortada e orientada.
    """
    x1, y1, x2, y2 = crop_box

    # Ordena coordenadas
    left = max(0, min(x1, x2))
    top = max(0, min(y1, y2))
    right = min(image.width, max(x1, x2))
    bottom = min(image.height, max(y1, y2))

    if right <= left or bottom <= top:
        raise ValueError("Área de recorte inválida ou com dimensões zero.")

    # 1. Rotação fina se ângulo diferente de zero
    processed = image
    if abs(rotation_angle) > 0.01:
        # Rotaciona expandindo para não cortar cantos antes do crop se desejado,
        # ou rotaciona mantendo o centro
        processed = processed.rotate(
            rotation_angle,
            resample=Image.BICUBIC,
            expand=False,
            fillcolor=(255, 255, 255, 0) if processed.mode == "RGBA" else (255, 255, 255)
        )

    # 2. Recorte
    cropped = processed.crop((left, top, right, bottom))
    _log.info(f"Imagem recortada de {image.size} para {cropped.size} com rotação {rotation_angle}°")
    return cropped


def process_image_file(
    source_path: Path,
    dest_path: Path,
    crop_box: Tuple[int, int, int, int],
    rotation_angle: float = 0.0,
    quality: int = 95
) -> Path:
    """
    Carrega imagem do disco, processa e grava no destino.

    Args:
        source_path: Caminho da imagem de entrada.
        dest_path: Caminho da imagem de saída.
        crop_box: Coordenadas (x1, y1, x2, y2).
        rotation_angle: Ângulo de rotação em graus.
        quality: Qualidade de salvamento (para JPEG/WebP).

    Returns:
        Caminho final gravado.
    """
    if not source_path.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {source_path}")

    with Image.open(source_path) as img:
        # Preserva orientação EXIF antes de rotacionar
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)

        result = apply_crop_and_rotation(img, crop_box, rotation_angle)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = dest_path.suffix.lstrip(".").upper()
        if fmt in ("JPG", "JPEG"):
            fmt = "JPEG"
            if result.mode in ("RGBA", "LA", "P"):
                result = result.convert("RGB")
            result.save(dest_path, format=fmt, quality=quality, optimize=True)
        elif fmt == "WEBP":
            result.save(dest_path, format="WEBP", quality=quality)
        elif fmt == "PNG":
            result.save(dest_path, format="PNG", optimize=True)
        else:
            result.save(dest_path)

    return dest_path
