"""
Testes unitários rigorosos para a lógica de images.annotate.

Valida a renderização de setas, retângulos, passos numerados e
filtros de censura (pixelização e desfoque gaussiano) sobre imagens reais.
"""
from pathlib import Path
from PIL import Image

from wintoolbox.tools.images.annotate.logic import (
    AnnotationItem,
    blur_region,
    pixelate_region,
    render_annotations,
)


def test_pixelate_and_blur_regions_real_effect():
    """Valida o efeito real de modificação de pixels de pixelização e desfoque."""
    # Imagem preta com quadrado branco central
    base = Image.new("RGB", (100, 100), (0, 0, 0))
    for x in range(30, 70):
        for y in range(30, 70):
            base.putpixel((x, y), (255, 255, 255))

    from PIL import ImageChops

    # Pixeliza região
    pixelated = pixelate_region(base, (20, 20, 80, 80), block_size=10)
    assert pixelated.size == (100, 100)
    diff_pix = ImageChops.difference(base, pixelated)
    assert diff_pix.getbbox() is not None

    # Desfoca região
    blurred = blur_region(base, (20, 20, 80, 80), radius=5)
    assert blurred.size == (100, 100)
    diff_blur = ImageChops.difference(base, blurred)
    assert diff_blur.getbbox() is not None


def test_render_annotations_all_types():
    """Valida renderização consolidada de múltiplos tipos de anotação."""
    base = Image.new("RGBA", (300, 300), (20, 20, 20, 255))

    annotations = [
        AnnotationItem(tool_type="rect", coords=(10, 10, 80, 80), color="#EF4444", width=3),
        AnnotationItem(tool_type="arrow", coords=(100, 100, 200, 200), color="#10B981", width=4),
        AnnotationItem(tool_type="step", coords=(50, 150, 50, 150), color="#3B82F6", step_num=1),
        AnnotationItem(tool_type="text", coords=(120, 30, 200, 60), color="#F59E0B", text="Nota"),
        AnnotationItem(tool_type="pixelate", coords=(220, 220, 280, 280)),
    ]

    result = render_annotations(base, annotations)
    assert result.size == (300, 300)
    assert result.mode == "RGBA"

    from PIL import ImageChops
    diff = ImageChops.difference(base, result)
    assert diff.getbbox() is not None


def test_annotation_item_serialization():
    """Valida o método to_dict do dataclass."""
    item = AnnotationItem(tool_type="arrow", coords=(0, 0, 10, 10), color="#FFFFFF", width=2)
    data = item.to_dict()
    assert data["tool_type"] == "arrow"
    assert data["coords"] == (0, 0, 10, 10)
    assert data["color"] == "#FFFFFF"
    assert data["width"] == 2
