"""
Testes unitários para a calculadora de telas, densidade de pixels (PPI) e proporções.
Diretrizes Anti-Gambiarra: Validação determinística de geometria óptica e proporções.
"""
from wintoolbox.tools.calc.screen.logic import (
    calculate_screen_metrics,
)


def test_screen_metrics_qhd_27():
    # 2560 x 1440 em 27 polegadas
    # Diag px = sqrt(2560^2 + 1440^2) = sqrt(6553600 + 2073600) = sqrt(8627200) = 2937.2095
    # PPI = 2937.2095 / 27 = 108.7855 -> 108.79
    res = calculate_screen_metrics(2560, 1440, 27.0)
    assert res["ppi"] == 108.79
    assert "16:9" in res["aspect_ratio"]
    assert res["escala_windows_sugerida"] == "100% (Padrão)"
    assert res["largura_cm"] == 59.77
    assert res["altura_cm"] == 33.62
    assert res["total_pixels_mp"] == 3.69


def test_screen_metrics_4k_15_6():
    # 3840 x 2160 em 15.6 polegadas (Notebook 4K)
    # Diag px = 4405.72 / 15.6 = 282.42 PPI -> HiDPI (200% a 250%)
    res = calculate_screen_metrics(3840, 2160, 15.6)
    assert res["ppi"] == 282.42
    assert "200% ou 250%" in res["escala_windows_sugerida"]
