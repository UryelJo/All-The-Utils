"""
Lógica pura para conversão e processamento de arquivos SVG.

Analisa metadados, dimensões e viewBox de vetores SVG e converte
imagens rasterizadas para pacotes ICO multi-resolução do Windows.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("images.svg_convert.logic")

DEFAULT_ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def parse_svg_dimensions(svg_path: Path) -> Tuple[int, int]:
    """
    Analisa um arquivo SVG e extrai sua resolução nativa ou dimensões de viewBox.

    Args:
        svg_path: Caminho para o arquivo .svg.

    Returns:
        Tupla (largura, altura) em pixels inteiros (padrão 512x512 se indeterminado).
    """
    if not svg_path.is_file():
        raise FileNotFoundError(f"Arquivo SVG não encontrado: {svg_path}")

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # 1. Tenta atributos explícitos width e height
        w_attr = root.get("width")
        h_attr = root.get("height")

        def _clean_dim(val: Optional[str]) -> Optional[int]:
            if not val:
                return None
            m = re.match(r"^([\d.]+)", val.strip())
            if m:
                return max(1, int(float(m.group(1))))
            return None

        w = _clean_dim(w_attr)
        h = _clean_dim(h_attr)

        if w and h:
            return (w, h)

        # 2. Tenta viewBox="min-x min-y width height"
        viewbox = root.get("viewBox") or root.get("viewbox")
        if viewbox:
            parts = [float(p) for p in re.split(r"[\s,]+", viewbox.strip()) if p]
            if len(parts) >= 4:
                vb_w = max(1, int(parts[2]))
                vb_h = max(1, int(parts[3]))
                return (vb_w, vb_h)

    except Exception as e:
        _log.warning(f"Não foi possível extrair dimensões exatas de {svg_path.name}: {e}")

    # Fallback seguro padrão para vetores de alta fidelidade
    return (512, 512)


def convert_png_to_multi_size_ico(
    png_path: Path,
    ico_path: Path,
    sizes: Optional[List[int]] = None
) -> Path:
    """
    Converte um arquivo PNG de alta resolução em um arquivo .ico do Windows multi-resolução.

    Args:
        png_path: Caminho da imagem PNG fonte.
        ico_path: Caminho de saída do .ico.
        sizes: Lista de dimensões (ex: [16, 24, 32, 48, 64, 128, 256]).

    Returns:
        Caminho do arquivo gravado.
    """
    if not png_path.is_file():
        raise FileNotFoundError(f"Arquivo PNG não encontrado: {png_path}")

    ico_sizes = sizes or DEFAULT_ICO_SIZES
    ico_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(png_path) as im:
        rgba = im.convert("RGBA")
        size_tuples = [(s, s) for s in ico_sizes]
        rgba.save(ico_path, format="ICO", sizes=size_tuples)

    return ico_path
