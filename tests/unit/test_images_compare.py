"""
Testes unitários rigorosos para a lógica de images.compare.

Valida métricas matemáticas determinísticas (MSE, PSNR, percentual de diferenças)
e composição do slider antes/depois.
"""
from PIL import Image

from wintoolbox.tools.images.compare.logic import (
    calculate_metrics,
    create_slider_composition,
    generate_diff_heatmap,
)


def test_calculate_metrics_identical_images():
    """Imagens idênticas devem ter MSE zero, PSNR máximo e status idêntico."""
    img_a = Image.new("RGB", (100, 100), (120, 120, 120))
    img_b = Image.new("RGB", (100, 100), (120, 120, 120))

    metrics = calculate_metrics(img_a, img_b)
    assert metrics.identical is True
    assert metrics.different_pixels_count == 0
    assert metrics.difference_percentage == 0.0
    assert metrics.mean_squared_error == 0.0
    assert metrics.psnr_db == 999.0


def test_calculate_metrics_different_images():
    """Imagens com pixels alterados devem calcular MSE e PSNR finitos reais."""
    img_a = Image.new("RGB", (10, 10), (0, 0, 0))
    img_b = Image.new("RGB", (10, 10), (0, 0, 0))
    # Altera 10 pixels (10% de 100)
    for x in range(10):
        img_b.putpixel((x, 0), (255, 255, 255))

    metrics = calculate_metrics(img_a, img_b)
    assert metrics.identical is False
    assert metrics.different_pixels_count == 10
    assert metrics.difference_percentage == 10.0
    assert metrics.mean_squared_error > 0.0
    assert 0 < metrics.psnr_db < 999.0


def test_create_slider_composition():
    """Valida que a composição do slider tem as dimensões corretas e mescla os dois lados."""
    img_a = Image.new("RGBA", (100, 50), (255, 0, 0, 255))  # Vermelho
    img_b = Image.new("RGBA", (100, 50), (0, 0, 255, 255))  # Azul

    comp = create_slider_composition(img_a, img_b, split_ratio=0.5, draw_line=False)
    assert comp.size == (100, 50)

    # Lado esquerdo deve ser vermelho da Imagem A
    assert comp.getpixel((10, 25))[:3] == (255, 0, 0)
    # Lado direito deve ser azul da Imagem B
    assert comp.getpixel((90, 25))[:3] == (0, 0, 255)


def test_generate_diff_heatmap():
    """Valida geração do mapa de calor de diferenças."""
    img_a = Image.new("RGB", (20, 20), (50, 50, 50))
    img_b = Image.new("RGB", (20, 20), (50, 50, 50))
    img_b.putpixel((5, 5), (150, 150, 150))

    heatmap = generate_diff_heatmap(img_a, img_b, amplification=2.0)
    assert heatmap.size == (20, 20)
    # Pixel com diferença deve ser amplificado (não-preto)
    assert heatmap.getpixel((5, 5)) != (0, 0, 0)
    # Pixel sem diferença deve ser preto puro
    assert heatmap.getpixel((0, 0)) == (0, 0, 0)
