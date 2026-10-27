"""
Lógica pura para cálculos de estatística descritiva e regressão linear simples.
Isolada de qualquer framework de interface gráfica.
"""
import math
import statistics
from typing import Any, Dict, List, Optional, Tuple


def parse_numeric_dataset(raw_text: str) -> List[float]:
    """
    Interpreta texto livre com números separados por vírgulas, ponto e vírgula, espaços ou novas linhas.
    Trata vírgulas decimais brasileiras quando apropriado.
    """
    if not raw_text.strip():
        return []

    # Normaliza separadores comuns
    cleaned = raw_text.replace(";", "\n").replace("\t", "\n")
    tokens = []

    # Se contém quebras de linha ou espaços, quebra por eles
    lines = cleaned.splitlines()
    for line in lines:
        for chunk in line.split():
            chunk = chunk.strip().rstrip(",")
            if not chunk:
                continue
            # Substitui vírgula decimal por ponto
            if "," in chunk and "." not in chunk:
                chunk = chunk.replace(",", ".")
            try:
                tokens.append(float(chunk))
            except ValueError:
                continue

    return tokens


def calculate_descriptive_statistics(data: List[float]) -> Dict[str, Any]:
    """
    Calcula métricas fundamentais de estatística descritiva uni-variada.
    """
    n = len(data)
    if n == 0:
        return {}

    sorted_data = sorted(data)
    total_sum = sum(data)
    mean = total_sum / n

    median = statistics.median(sorted_data)

    try:
        mode_val = statistics.mode(data)
        mode_str = f"{mode_val:g}"
    except statistics.StatisticsError:
        mode_str = "Amodal"

    min_val = sorted_data[0]
    max_val = sorted_data[-1]
    amplitude = max_val - min_val

    if n > 1:
        var_sample = statistics.variance(data)
        stdev_sample = statistics.stdev(data)
        std_error = stdev_sample / math.sqrt(n)
    else:
        var_sample = 0.0
        stdev_sample = 0.0
        std_error = 0.0

    var_pop = statistics.pvariance(data)
    stdev_pop = statistics.pstdev(data)

    # Quartis
    if n >= 4:
        quantiles = statistics.quantiles(sorted_data, n=4, method="inclusive")
        q1, q2, q3 = quantiles[0], quantiles[1], quantiles[2]
        iqr = q3 - q1
    else:
        q1, q2, q3, iqr = min_val, median, max_val, amplitude

    return {
        "count": n,
        "sum": round(total_sum, 4),
        "mean": round(mean, 4),
        "median": round(median, 4),
        "mode": mode_str,
        "min": min_val,
        "max": max_val,
        "range": round(amplitude, 4),
        "var_sample": round(var_sample, 4),
        "var_pop": round(var_pop, 4),
        "stdev_sample": round(stdev_sample, 4),
        "stdev_pop": round(stdev_pop, 4),
        "std_error": round(std_error, 4),
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
    }


def calculate_linear_regression(x_data: List[float], y_data: List[float]) -> Dict[str, Any]:
    """
    Calcula a regressão linear simples (Método dos Mínimos Quadrados) entre X e Y.
    """
    n = min(len(x_data), len(y_data))
    if n < 2:
        return {"error": "É necessário pelo menos 2 pares de dados (X, Y) válidos."}

    x = x_data[:n]
    y = y_data[:n]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerador = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominador_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    denominador_y = sum((y[i] - mean_y) ** 2 for i in range(n))

    if denominador_x == 0:
        return {"error": "Variância de X é zero (todos os valores de X são idênticos)."}

    slope = numerador / denominador_x
    intercept = mean_y - (slope * mean_x)

    # Correlação de Pearson (r)
    if denominador_x > 0 and denominador_y > 0:
        r = numerador / math.sqrt(denominador_x * denominador_y)
        r_squared = r ** 2
    else:
        r = 0.0
        r_squared = 0.0

    eq_str = f"y = {slope:.4f}x {'+' if intercept >= 0 else '-'} {abs(intercept):.4f}"

    return {
        "n": n,
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "correlation_r": round(r, 6),
        "r_squared": round(r_squared, 6),
        "equation": eq_str
    }
