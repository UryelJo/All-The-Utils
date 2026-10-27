"""
Testes unitários rigorosos para o Gerador de Paletas Harmônicas e Contraste WCAG (dev.color_palette_generator).
Validações matemáticas de HSL/RGB, luminância relativa sRGB e harmonia de cores.
"""
import pytest

from wintoolbox.tools.dev.color_palette_generator.logic import (
    calculate_contrast_ratio,
    export_palette_code,
    generate_palette,
    hex_to_rgb,
    hsl_to_rgb,
    rgb_to_hex,
    rgb_to_hsl,
)
from wintoolbox.tools.dev.color_palette_generator.tool import ColorPaletteGeneratorTool


def test_color_space_conversions_exact():
    # Branco puro
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert rgb_to_hex(255, 255, 255) == "#FFFFFF"

    # Preto puro
    assert hex_to_rgb("#000000") == (0, 0, 0)
    assert rgb_to_hex(0, 0, 0) == "#000000"

    # Vermelho primário
    r, g, b = hex_to_rgb("#FF0000")
    h, s, l = rgb_to_hsl(r, g, b)
    assert h == 0.0
    assert s == 1.0
    assert l == 0.5
    assert hsl_to_rgb(h, s, l) == (255, 0, 0)


def test_wcag_contrast_ratio_exact():
    # Preto sobre Branco = 21.0:1
    contrast_bw = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert contrast_bw["ratio"] == 21.0
    assert contrast_bw["wcag_aa_normal"] is True
    assert contrast_bw["wcag_aaa_normal"] is True

    # Branco sobre Branco = 1.0:1
    contrast_ww = calculate_contrast_ratio("#FFFFFF", "#FFFFFF")
    assert contrast_ww["ratio"] == 1.0
    assert contrast_ww["wcag_aa_normal"] is False


def test_generate_palette_harmonies():
    base_blue = "#3B82F6"

    # Complementar: deve conter a base e a complementar
    comp = generate_palette(base_blue, "complementary")
    assert len(comp) == 4
    assert comp[0]["label"] == "Base"
    assert comp[1]["label"] == "Complementar"

    # Triádica: 3 cores
    triadic = generate_palette(base_blue, "triadic")
    assert len(triadic) == 3

    # Monocromática: 5 variações de luminosidade
    mono = generate_palette(base_blue, "monochromatic")
    assert len(mono) == 5


def test_export_palette_code_css():
    palette = [
        {"label": "Base", "hex": "#3B82F6"},
        {"label": "Complementar", "hex": "#F6B03B"},
    ]
    css = export_palette_code(palette, "css")
    assert ":root {" in css
    assert "--color-base: #3B82F6;" in css
    assert "--color-complementar: #F6B03B;" in css


def test_color_palette_tool_ui(qtbot):
    tool = ColorPaletteGeneratorTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Verifica se os swatches foram gerados
    assert view._swatches_layout.count() >= 3
    assert ":root {" in view._txt_code.toPlainText()

    # Altera para paleta triádica
    view._combo_harmony.setCurrentIndex(2)  # Triádica
    assert len(view._current_palette) == 3
