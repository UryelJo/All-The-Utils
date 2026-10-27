"""
Lógica pura para comparador econômico de combustíveis (Etanol vs. Gasolina) e estimador de custos de viagem.
Desacoplada de frameworks de interface gráfica.
"""
from typing import Any, Dict


def calculate_fuel_advantage(
    preco_etanol: float,
    preco_gasolina: float,
    fator_eficiencia: float = 0.70
) -> Dict[str, Any]:
    """
    Compara economicamente o abastecimento com Etanol ou Gasolina.
    fator_eficiencia: padrão 0.70 (70%) para motores flex padrão, ou específico do veículo.
    """
    if preco_gasolina <= 0 or preco_etanol <= 0:
        return {
            "relacao_percentual": 0.0,
            "recomendacao": "Dados Inválidos",
            "preco_limite_etanol": 0.0,
            "diferenca_percentual": 0.0,
            "vantagem_etanol": False
        }

    relacao = round((preco_etanol / preco_gasolina) * 100.0, 2)
    preco_limite = round(preco_gasolina * fator_eficiencia, 2)
    vantagem_etanol = preco_etanol <= preco_limite

    diferenca_pct = round(abs(relacao - (fator_eficiencia * 100.0)), 2)

    if vantagem_etanol:
        recomendacao = f"Abasteça com ETANOL (Relação de {relacao:.1f}% vs limite de {fator_eficiencia * 100:.0f}%)"
    else:
        recomendacao = f"Abasteça com GASOLINA (Relação de {relacao:.1f}% vs limite de {fator_eficiencia * 100:.0f}%)"

    return {
        "relacao_percentual": relacao,
        "recomendacao": recomendacao,
        "preco_limite_etanol": preco_limite,
        "diferenca_percentual": diferenca_pct,
        "vantagem_etanol": vantagem_etanol
    }


def calculate_trip_cost(
    distancia_km: float,
    consumo_km_l: float,
    preco_combustivel: float,
    pedagios_total: float = 0.0,
    num_passageiros: int = 1
) -> Dict[str, Any]:
    """
    Calcula consumo de combustível, custo total de viagem e divisão por passageiro.
    """
    if distancia_km <= 0 or consumo_km_l <= 0 or preco_combustivel <= 0:
        return {
            "litros_necessarios": 0.0,
            "custo_combustivel": 0.0,
            "custo_total": 0.0,
            "custo_por_passageiro": 0.0,
            "custo_por_km": 0.0
        }

    passageiros = max(1, num_passageiros)
    litros = round(distancia_km / consumo_km_l, 2)
    custo_comb = round(litros * preco_combustivel, 2)
    custo_tot = round(custo_comb + pedagios_total, 2)
    custo_pass = round(custo_tot / passageiros, 2)
    custo_km = round(custo_tot / distancia_km, 2)

    return {
        "litros_necessarios": litros,
        "custo_combustivel": custo_comb,
        "custo_total": custo_tot,
        "custo_por_passageiro": custo_pass,
        "custo_por_km": custo_km
    }
