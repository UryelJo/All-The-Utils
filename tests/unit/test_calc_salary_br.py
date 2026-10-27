"""
Testes unitários para a calculadora salarial CLT brasileira.
Diretrizes Anti-Gambiarra: Cálculos matemáticos determinísticos e validação de regras CLT.
"""
from wintoolbox.tools.calc.salary_br.logic import (
    calculate_ferias,
    calculate_folha_pagamento,
    calculate_inss_progressive,
    calculate_irrf,
    calculate_rescisao,
)


def test_inss_progressive():
    # Salário mínimo R$ 1.412,00 -> 7,5% = 105,90
    inss, aliq = calculate_inss_progressive(1412.00)
    assert inss == 105.90
    assert aliq == 7.50

    # Salário R$ 3.000,00:
    # 1ª faixa: 1412 * 0.075 = 105.90
    # 2ª faixa: (2666.68 - 1412) * 0.09 = 1254.68 * 0.09 = 112.9212
    # 3ª faixa: (3000 - 2666.68) * 0.12 = 333.32 * 0.12 = 39.9984
    # Total = 105.90 + 112.92 + 40.00 = 258.82
    inss3k, aliq3k = calculate_inss_progressive(3000.00)
    assert inss3k == 258.82
    assert aliq3k == 8.63


def test_irrf_calculation():
    # Base isenta R$ 2.200,00
    irrf, aliq, metodo = calculate_irrf(2200.00)
    assert irrf == 0.0
    assert aliq == 0.0

    # Base R$ 4.000,00 sem dependentes
    irrf_val, aliq_val, metodo_val = calculate_irrf(4000.00, dependentes=0)
    assert irrf_val > 0.0
    assert metodo_val in ["Deduções Legais", "Desconto Simplificado"]


def test_folha_pagamento_full():
    res = calculate_folha_pagamento(salario_bruto=5000.00, dependentes=1, outros_descontos=100.0)
    assert res["salario_bruto"] == 5000.00
    assert res["fgts"] == 400.00  # 8% de 5000
    assert res["inss"] > 0.0
    assert res["irrf"] >= 0.0
    assert res["salario_liquido"] == round(5000.00 - res["total_descontos"], 2)


def test_ferias_calculation():
    res = calculate_ferias(salario_bruto=3000.00, dias_ferias=30, abono_pecuniario_dias=0)
    assert res["valor_gozo"] == 3000.00
    assert res["terco_constitucional"] == 1000.00
    assert res["total_bruto"] == 4000.00
    assert res["total_liquido"] == round(4000.00 - res["total_descontos"], 2)


def test_rescisao_calculation():
    res = calculate_rescisao(
        salario_bruto=3000.00,
        meses_trabalhados=12,
        tipo_motivo="sem_justa_causa",
        saldo_salario_dias=10
    )
    assert res["saldo_salario"] == 1000.00  # 10 dias de 3000/30
    assert res["aviso_previo"] == 3000.00
    assert res["multa_fgts"] > 0.0
    assert res["total_liquido"] > 0.0
