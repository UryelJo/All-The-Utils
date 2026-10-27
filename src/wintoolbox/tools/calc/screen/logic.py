"""
Lógica pura para cálculos de parâmetros ópticos de telas e monitores:
Densidade de pixels (PPI), Proporção de Tela (Aspect Ratio), Dimensões físicas e Escala recomendada de DPI no Windows.
Desacoplada de frameworks de interface gráfica.
"""
import math
from typing import Any, Dict


def calculate_screen_metrics(
    largura_px: int,
    altura_px: int,
    diagonal_polegadas: float
) -> Dict[str, Any]:
    """
    Calcula PPI, Aspect Ratio reduzido por MDC, dimensões físicas em centímetros e escala sugerida no Windows.
    """
    if largura_px <= 0 or altura_px <= 0 or diagonal_polegadas <= 0:
        return {
            "ppi": 0.0,
            "aspect_ratio": "0:0",
            "largura_cm": 0.0,
            "altura_cm": 0.0,
            "area_cm2": 0.0,
            "total_pixels_mp": 0.0,
            "escala_windows_sugerida": "100%"
        }

    # Diagonal em pixels
    diag_px = math.sqrt((largura_px ** 2) + (altura_px ** 2))
    ppi = round(diag_px / diagonal_polegadas, 2)

    # Proporção reduzida
    mdc = math.gcd(largura_px, altura_px)
    ratio_w = largura_px // mdc
    ratio_h = altura_px // mdc

    # Simplificações comuns para monitores ultrawide (ex: 21:9 em vez de 64:27)
    ratio_float = largura_px / altura_px
    if abs(ratio_float - (16.0 / 9.0)) < 0.02:
        ratio_str = "16:9 (Widescreen)"
    elif abs(ratio_float - (16.0 / 10.0)) < 0.02:
        ratio_str = "16:10"
    elif abs(ratio_float - (21.0 / 9.0)) < 0.05 or abs(ratio_float - (64.0 / 27.0)) < 0.02:
        ratio_str = "21:9 (Ultrawide)"
    elif abs(ratio_float - (32.0 / 9.0)) < 0.05:
        ratio_str = "32:9 (Super Ultrawide)"
    elif abs(ratio_float - (4.0 / 3.0)) < 0.02:
        ratio_str = "4:3 (Clássico)"
    elif abs(ratio_float - (3.0 / 2.0)) < 0.02:
        ratio_str = "3:2 (Microsoft Surface)"
    else:
        ratio_str = f"{ratio_w}:{ratio_h}"

    # Dimensões físicas em cm
    # arctan(H / W)
    theta = math.atan(altura_px / largura_px)
    w_pol = diagonal_polegadas * math.cos(theta)
    h_pol = diagonal_polegadas * math.sin(theta)

    w_cm = round(w_pol * 2.54, 2)
    h_cm = round(h_pol * 2.54, 2)
    area_cm2 = round(w_cm * h_cm, 2)

    total_mp = round((largura_px * altura_px) / 1_000_000.0, 2)

    # Escala recomendada de DPI no Windows
    if ppi < 115.0:
        escala_win = "100% (Padrão)"
    elif ppi < 145.0:
        escala_win = "125%"
    elif ppi < 185.0:
        escala_win = "150%"
    elif ppi < 235.0:
        escala_win = "175% ou 200%"
    else:
        escala_win = "200% ou 250% (HiDPI)"

    return {
        "ppi": ppi,
        "aspect_ratio": ratio_str,
        "largura_cm": w_cm,
        "altura_cm": h_cm,
        "area_cm2": area_cm2,
        "total_pixels_mp": total_mp,
        "escala_windows_sugerida": escala_win
    }
