"""
Testes unitários para a calculadora de saúde, metabolismo e hidratação.
Diretrizes Anti-Gambiarra: Validação determinística de equações biométricas.
"""
from wintoolbox.tools.calc.health.logic import (
    calculate_imc,
    calculate_tdee_and_goals,
    calculate_tmb_mifflin_st_jeor,
    calculate_water_intake,
)


def test_calculate_imc():
    # 70 kg, 175 cm -> IMC = 70 / (1.75 ** 2) = 22.86
    imc, classificacao, peso_ideal = calculate_imc(70.0, 175.0)
    assert imc == 22.86
    assert classificacao == "Peso normal"
    assert "56.7 kg a 76.3 kg" in peso_ideal

    # 100 kg, 175 cm -> IMC = 32.65 (Obesidade Grau I)
    imc_obeso, class_obeso, _ = calculate_imc(100.0, 175.0)
    assert imc_obeso == 32.65
    assert class_obeso == "Obesidade Grau I"


def test_calculate_tmb_mifflin_st_jeor():
    # Homem: 80 kg, 180 cm, 30 anos
    # (10 * 80) + (6.25 * 180) - (5 * 30) + 5 = 800 + 1125 - 150 + 5 = 1780.0
    tmb_m = calculate_tmb_mifflin_st_jeor(80.0, 180.0, 30, sexo="M")
    assert tmb_m == 1780.0

    # Mulher: 60 kg, 165 cm, 25 anos
    # (10 * 60) + (6.25 * 165) - (5 * 25) - 161 = 600 + 1031.25 - 125 - 161 = 1345.25 -> 1345.2
    tmb_f = calculate_tmb_mifflin_st_jeor(60.0, 165.0, 25, sexo="F")
    assert tmb_f == 1345.2


def test_calculate_tdee_and_goals():
    tmb = 1800.0
    res = calculate_tdee_and_goals(tmb, nivel_atividade="moderado")
    # 1800 * 1.55 = 2790.0
    assert res["tdee_manutencao"] == 2790.0
    assert res["emagrecimento_moderado"] == 2290.0  # 2790 - 500
    assert res["hipertrofia_ganho"] == 3140.0       # 2790 + 350


def test_calculate_water_intake():
    # 70 kg, 0 min treino -> 70 * 35 = 2450 ml = 2.45 L
    w1 = calculate_water_intake(70.0, exercicio_minutos=0)
    assert w1["total_ml"] == 2450
    assert w1["total_litros"] == 2.45
    assert w1["copos_250ml"] == 10

    # 70 kg, 45 min treino -> 2450 + 500 = 2950 ml
    w2 = calculate_water_intake(70.0, exercicio_minutos=45)
    assert w2["total_ml"] == 2950
