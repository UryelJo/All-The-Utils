"""
Testes unitários para a calculadora de combustível e custos de viagem.
Diretrizes Anti-Gambiarra: Validação determinística de paridade econômica e consumo.
"""
from wintoolbox.tools.calc.fuel.logic import (
    calculate_fuel_advantage,
    calculate_trip_cost,
)


def test_fuel_advantage_etanol_wins():
    # Gasolina R$ 6,00, Etanol R$ 4,00 (4.00 / 6.00 = 66.67% < 70%)
    res = calculate_fuel_advantage(preco_etanol=4.00, preco_gasolina=6.00, fator_eficiencia=0.70)
    assert res["relacao_percentual"] == 66.67
    assert res["preco_limite_etanol"] == 4.20
    assert res["vantagem_etanol"] is True
    assert "ETANOL" in res["recomendacao"]


def test_fuel_advantage_gasolina_wins():
    # Gasolina R$ 5,00, Etanol R$ 3,80 (3.80 / 5.00 = 76% > 70%)
    res = calculate_fuel_advantage(preco_etanol=3.80, preco_gasolina=5.00, fator_eficiencia=0.70)
    assert res["relacao_percentual"] == 76.00
    assert res["preco_limite_etanol"] == 3.50
    assert res["vantagem_etanol"] is False
    assert "GASOLINA" in res["recomendacao"]


def test_trip_cost():
    # Distância: 400 km, Consumo: 10 km/l -> 40 Litros
    # Preço: R$ 5,00/l -> Combustível = R$ 200,00
    # Pedágio: R$ 50,00 -> Total = R$ 250,00
    # 2 passageiros -> R$ 125,00 cada
    res = calculate_trip_cost(
        distancia_km=400.0,
        consumo_km_l=10.0,
        preco_combustivel=5.00,
        pedagios_total=50.00,
        num_passageiros=2
    )

    assert res["litros_necessarios"] == 40.0
    assert res["custo_combustivel"] == 200.00
    assert res["custo_total"] == 250.00
    assert res["custo_por_passageiro"] == 125.00
    assert res["custo_por_km"] == 0.62  # 250 / 400 = 0.625 -> 0.62
