"""
Testes unitários para a calculadora estatística e regressão linear.
Diretrizes Anti-Gambiarra: Validação determinística de métricas matemáticas.
"""
from wintoolbox.tools.calc.statistics.logic import (
    calculate_descriptive_statistics,
    calculate_linear_regression,
    parse_numeric_dataset,
)


def test_parse_numeric_dataset():
    raw = "10, 20.5; 30 \n 40,5"
    res = parse_numeric_dataset(raw)
    assert res == [10.0, 20.5, 30.0, 40.5]


def test_descriptive_statistics():
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    res = calculate_descriptive_statistics(data)

    assert res["count"] == 8
    assert res["sum"] == 40.0
    assert res["mean"] == 5.0
    assert res["median"] == 4.5
    assert res["mode"] == "4"
    assert res["min"] == 2.0
    assert res["max"] == 9.0
    assert res["range"] == 7.0
    assert res["var_sample"] == 4.5714
    assert res["stdev_sample"] == 2.1381
    assert res["var_pop"] == 4.0
    assert res["stdev_pop"] == 2.0


def test_linear_regression():
    # Dados perfeitamente lineares: y = 2x + 1
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [3.0, 5.0, 7.0, 9.0, 11.0]

    res = calculate_linear_regression(x, y)
    assert res["n"] == 5
    assert res["slope"] == 2.0
    assert res["intercept"] == 1.0
    assert res["r_squared"] == 1.0
    assert res["correlation_r"] == 1.0
    assert "y = 2.0000x + 1.0000" in res["equation"]
