"""
Testes unitários para a calculadora elétrica residencial, Lei de Ohm e resistores.
Diretrizes Anti-Gambiarra: Validação determinística de fórmulas da física e código EIA de resistores.
"""
from wintoolbox.tools.calc.electrical.logic import (
    calculate_energy_consumption,
    calculate_ohm_law,
    calculate_resistor_value,
)


def test_energy_consumption():
    # 1000 W por 5 horas/dia por 30 dias -> 150 kWh/mês
    # Tarifa R$ 1,00 -> Custo R$ 150,00/mês, R$ 1.800,00/ano
    res = calculate_energy_consumption(
        potencia_watts=1000.0,
        horas_por_dia=5.0,
        dias_no_mes=30,
        tarifa_kwh=1.0
    )
    assert res["consumo_diario_kwh"] == 5.0
    assert res["consumo_mensal_kwh"] == 150.0
    assert res["custo_mensal"] == 150.0
    assert res["custo_anual"] == 1800.0


def test_ohm_law():
    # V = 120 V, R = 10 Ω -> I = 12 A, P = 1440 W
    res_vr = calculate_ohm_law(tensao_v=120.0, resistencia_ohm=10.0)
    assert res_vr["corrente_a"] == 12.0
    assert res_vr["potencia_w"] == 1440.0

    # I = 2 A, P = 100 W -> V = 50 V, R = 25 Ω
    res_ip = calculate_ohm_law(corrente_a=2.0, potencia_w=100.0)
    assert res_ip["tensao_v"] == 50.0
    assert res_ip["resistencia_ohm"] == 25.0


def test_resistor_4_bands():
    # Marrom (1), Preto (0), Vermelho (x100), Dourado (±5%) -> 10 * 100 = 1000 Ω = 1 kΩ ±5%
    r1 = calculate_resistor_value("Marrom", "Preto", "Vermelho", "Dourado")
    assert r1["valor_ohms"] == 1000.0
    assert "1 kΩ ±5%" in r1["formatado"]
    assert r1["valor_minimo"] == 950.0
    assert r1["valor_maximo"] == 1050.0


def test_resistor_5_bands():
    # Amarelo (4), Violeta (7), Preto (0), Laranja (x1000), Marrom (±1%)
    # 470 * 1000 = 470.000 Ω = 470 kΩ ±1%
    r2 = calculate_resistor_value("Amarelo", "Violeta", "Laranja", "Marrom", faixa3="Preto")
    assert r2["valor_ohms"] == 470000.0
    assert "470 kΩ ±1%" in r2["formatado"]
    assert r2["tolerancia_pct"] == 1.0
