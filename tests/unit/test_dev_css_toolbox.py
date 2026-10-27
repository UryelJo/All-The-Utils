"""
Testes unitários para dev.css_toolbox.
Valida cálculos de tipografia fluida clamp, conversão px/rem e acessibilidade de contraste WCAG.
"""
import pytest
from wintoolbox.tools.dev.css_toolbox.logic import (
    calculate_contrast_ratio,
    calculate_fluid_clamp,
    generate_box_shadow_css,
    generate_linear_gradient_css,
    hex_to_rgb,
    px_to_rem,
    rem_to_px,
)


def test_calculate_fluid_clamp():
    """Valida cálculo determinístico da expressão clamp()."""
    expr = calculate_fluid_clamp(
        min_size_px=16.0,
        max_size_px=32.0,
        min_viewport_px=320.0,
        max_viewport_px=1200.0,
        root_font_size=16.0
    )
    assert expr.startswith("clamp(1.0000rem,")
    assert "2.0000rem)" in expr
    assert "vw" in expr

    with pytest.raises(ValueError):
        calculate_fluid_clamp(16.0, 32.0, min_viewport_px=1200.0, max_viewport_px=320.0)


def test_px_and_rem_conversion():
    """Valida conversões bidirecionais de unidades."""
    assert px_to_rem(16.0, base_px=16.0) == 1.0
    assert px_to_rem(24.0, base_px=16.0) == 1.5
    assert rem_to_px(2.0, base_px=16.0) == 32.0


def test_wcag_contrast_ratio():
    """Valida taxa de contraste matemático WCAG 2.1."""
    # Preto sobre branco deve ser exatamente 21:1
    ratio_max = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert round(ratio_max, 1) == 21.0

    # Mesma cor deve ser 1:1
    ratio_same = calculate_contrast_ratio("#FFFFFF", "#FFFFFF")
    assert round(ratio_same, 1) == 1.0

    # Texto escuro sobre fundo claro
    ratio = calculate_contrast_ratio("#1E293B", "#FFFFFF")
    assert ratio > 7.0  # Passa em AAA


def test_css_generators():
    """Valida sintaxe gerada de sombras e gradientes."""
    grad = generate_linear_gradient_css(90, [("#FF0000", 0), ("#0000FF", 100)])
    assert grad == "background: linear-gradient(90deg, #FF0000 0%, #0000FF 100%);"

    sh = generate_box_shadow_css(0, 4, 12, 0, "rgba(0, 0, 0, 0.1)", inset=False)
    assert sh == "box-shadow: 0px 4px 12px 0px rgba(0, 0, 0, 0.1);"

    sh_inset = generate_box_shadow_css(1, 2, 3, 4, "#000", inset=True)
    assert sh_inset == "box-shadow: inset 1px 2px 3px 4px #000;"
