"""
Lógica pura para cálculos elétricos residenciais, Lei de Ohm e código de cores de resistores.
Desacoplada de frameworks de interface gráfica.
"""
import math
from typing import Any, Dict, Optional, Tuple

# Tabela oficial de código de cores de resistores (EIA-RS-279)
RESISTOR_DIGITS = {
    "Preto": 0,
    "Marrom": 1,
    "Vermelho": 2,
    "Laranja": 3,
    "Amarelo": 4,
    "Verde": 5,
    "Azul": 6,
    "Violeta": 7,
    "Cinza": 8,
    "Branco": 9,
}

RESISTOR_MULTIPLIERS = {
    "Preto": 1.0,
    "Marrom": 10.0,
    "Vermelho": 100.0,
    "Laranja": 1000.0,
    "Amarelo": 10000.0,
    "Verde": 100000.0,
    "Azul": 1000000.0,
    "Violeta": 10000000.0,
    "Dourado": 0.1,
    "Prateado": 0.01,
}

RESISTOR_TOLERANCES = {
    "Marrom": 1.0,
    "Vermelho": 2.0,
    "Verde": 0.5,
    "Azul": 0.25,
    "Violeta": 0.1,
    "Dourado": 5.0,
    "Prateado": 10.0,
}


def calculate_energy_consumption(
    potencia_watts: float,
    horas_por_dia: float,
    dias_no_mes: int = 30,
    tarifa_kwh: float = 0.85
) -> Dict[str, Any]:
    """
    Calcula o consumo mensal em kWh e o custo projetado na conta de luz.
    """
    if potencia_watts <= 0 or horas_por_dia <= 0 or dias_no_mes <= 0:
        return {
            "consumo_diario_kwh": 0.0,
            "consumo_mensal_kwh": 0.0,
            "custo_mensal": 0.0,
            "custo_anual": 0.0
        }

    kwh_dia = (potencia_watts * horas_por_dia) / 1000.0
    kwh_mes = kwh_dia * dias_no_mes
    custo_mes = kwh_mes * tarifa_kwh
    custo_ano = custo_mes * 12.0

    return {
        "consumo_diario_kwh": round(kwh_dia, 3),
        "consumo_mensal_kwh": round(kwh_mes, 2),
        "custo_mensal": round(custo_mes, 2),
        "custo_anual": round(custo_ano, 2)
    }


def calculate_ohm_law(
    tensao_v: Optional[float] = None,
    corrente_a: Optional[float] = None,
    resistencia_ohm: Optional[float] = None,
    potencia_w: Optional[float] = None
) -> Dict[str, float]:
    """
    Calcula as grandezas elétricas restantes a partir de 2 grandezas fornecidas (Lei de Ohm).
    """
    v, i, r, p = tensao_v, corrente_a, resistencia_ohm, potencia_w

    if v is not None and i is not None and v > 0 and i > 0:
        r = v / i
        p = v * i
    elif v is not None and r is not None and v > 0 and r > 0:
        i = v / r
        p = (v ** 2) / r
    elif v is not None and p is not None and v > 0 and p > 0:
        i = p / v
        r = (v ** 2) / p
    elif i is not None and r is not None and i > 0 and r > 0:
        v = i * r
        p = (i ** 2) * r
    elif i is not None and p is not None and i > 0 and p > 0:
        v = p / i
        r = p / (i ** 2)
    elif r is not None and p is not None and r > 0 and p > 0:
        v = math.sqrt(p * r)
        i = math.sqrt(p / r)
    else:
        return {}

    return {
        "tensao_v": round(v, 4),
        "corrente_a": round(i, 4),
        "resistencia_ohm": round(r, 4),
        "potencia_w": round(p, 4)
    }


def calculate_resistor_value(
    faixa1: str,
    faixa2: str,
    multiplicador: str,
    tolerancia: str = "Dourado",
    faixa3: Optional[str] = None
) -> Dict[str, Any]:
    """
    Decodifica o valor de resistência e tolerância para resistores de 4 ou 5 faixas.
    """
    d1 = RESISTOR_DIGITS.get(faixa1, 0)
    d2 = RESISTOR_DIGITS.get(faixa2, 0)

    if faixa3:
        d3 = RESISTOR_DIGITS.get(faixa3, 0)
        base_num = (d1 * 100) + (d2 * 10) + d3
    else:
        base_num = (d1 * 10) + d2

    mult = RESISTOR_MULTIPLIERS.get(multiplicador, 1.0)
    tol = RESISTOR_TOLERANCES.get(tolerancia, 5.0)

    valor_ohms = base_num * mult

    if valor_ohms >= 1_000_000:
        fmt_str = f"{valor_ohms / 1_000_000:g} MΩ"
    elif valor_ohms >= 1_000:
        fmt_str = f"{valor_ohms / 1_000:g} kΩ"
    else:
        fmt_str = f"{valor_ohms:g} Ω"

    min_val = round(valor_ohms * (1.0 - (tol / 100.0)), 2)
    max_val = round(valor_ohms * (1.0 + (tol / 100.0)), 2)

    return {
        "valor_ohms": round(valor_ohms, 2),
        "formatado": f"{fmt_str} ±{tol:g}%",
        "tolerancia_pct": tol,
        "valor_minimo": min_val,
        "valor_maximo": max_val
    }
