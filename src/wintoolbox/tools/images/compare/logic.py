"""
Lógica pura para comparação e cálculo de diferenças entre duas imagens.

Calcula diferença absoluta de pixels, métricas de fidelidade (MSE, PSNR)
e composição em slider antes/depois.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageChops, ImageDraw

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("images.compare.logic")


@dataclass
class ComparisonMetrics:
    """Métricas numéricas de comparação entre duas imagens."""
    width: int
    height: int
    different_pixels_count: int
    total_pixels: int
    difference_percentage: float
    mean_squared_error: float
    psnr_db: float  # Peak Signal-to-Noise Ratio (inf se idênticas)
    identical: bool


def calculate_metrics(img_a: Image.Image, img_b: Image.Image) -> ComparisonMetrics:
    """Calcula métricas matemáticas de diferença entre duas imagens de mesmo tamanho."""
    a = img_a.convert("RGB")
    b = img_b.convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, resample=Image.LANCZOS)

    w, h = a.size
    total_pixels = w * h

    diff_img = ImageChops.difference(a, b)
    diff_pixels = diff_img.load()

    sum_sq_err = 0.0
    different_count = 0

    for x in range(w):
        for y in range(h):
            r, g, bl = diff_pixels[x, y]
            err = (r * r + g * g + bl * bl) / 3.0
            if err > 0.0:
                different_count += 1
                sum_sq_err += err

    mse = sum_sq_err / total_pixels if total_pixels > 0 else 0.0

    if mse == 0.0:
        psnr = float("inf")
    else:
        psnr = 20.0 * math.log10(255.0 / math.sqrt(mse))

    diff_pct = (different_count / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    return ComparisonMetrics(
        width=w,
        height=h,
        different_pixels_count=different_count,
        total_pixels=total_pixels,
        difference_percentage=round(diff_pct, 3),
        mean_squared_error=round(mse, 3),
        psnr_db=round(psnr, 2) if psnr != float("inf") else 999.0,
        identical=(different_count == 0),
    )


def generate_diff_heatmap(img_a: Image.Image, img_b: Image.Image, amplification: float = 3.0) -> Image.Image:
    """
    Gera um mapa de calor visual onde diferenças são destacadas sobre fundo preto.
    """
    a = img_a.convert("RGB")
    b = img_b.convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, resample=Image.LANCZOS)

    diff = ImageChops.difference(a, b)

    if amplification > 1.0:
        diff = diff.point(lambda p: min(255, int(p * amplification)))

    return diff


def generate_diff_overlay(
    img_a: Image.Image,
    img_b: Image.Image,
    amplification: float = 3.0,
    show_ghost_base: bool = True
) -> Image.Image:
    """
    Gera imagem de diferenças com opção de fundo fantasma suavizado (ghost background).
    Diferenças sutis são destacadas em magenta vibrante sobre a imagem base esmaecida.
    """
    a = img_a.convert("RGB")
    b = img_b.convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, resample=Image.LANCZOS)

    diff = ImageChops.difference(a, b)
    if amplification > 1.0:
        diff = diff.point(lambda p: min(255, int(p * amplification)))

    if not show_ghost_base:
        return diff

    # Imagem base em escala de cinza escurecida (25% de luminosidade)
    ghost = a.convert("L").convert("RGB")
    ghost = ghost.point(lambda p: int(p * 0.25))

    # Cria máscara para os pixels diferentes
    diff_gray = diff.convert("L")
    mask = diff_gray.point(lambda p: min(255, int(p * 2)) if p > 2 else 0)

    # Cor de destaque: magenta/neon (#E11D48 / #EC4899)
    highlight = Image.new("RGB", a.size, (236, 72, 153))

    result = ghost.copy()
    result.paste(highlight, (0, 0), mask=mask)
    return result


def create_slider_composition(
    img_a: Image.Image,
    img_b: Image.Image,
    split_ratio: float = 0.5,
    draw_line: bool = True
) -> Image.Image:
    """
    Combina a Imagem A (à esquerda) e a Imagem B (à direita) em uma única imagem composta dividida pelo split_ratio.
    """
    a = img_a.convert("RGBA")
    b = img_b.convert("RGBA")
    if a.size != b.size:
        b = b.resize(a.size, resample=Image.LANCZOS)

    w, h = a.size
    split_x = max(0, min(w, int(w * split_ratio)))

    result = Image.new("RGBA", (w, h))

    if split_x > 0:
        part_a = a.crop((0, 0, split_x, h))
        result.paste(part_a, (0, 0))

    if split_x < w:
        part_b = b.crop((split_x, 0, w, h))
        result.paste(part_b, (split_x, 0))

    if draw_line and 0 < split_x < w:
        draw = ImageDraw.Draw(result)
        draw.line([(split_x, 0), (split_x, h)], fill=(255, 255, 255, 220), width=2)

    return result
