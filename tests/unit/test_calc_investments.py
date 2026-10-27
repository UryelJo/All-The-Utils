"""
Testes unitários para o simulador de investimentos de renda fixa e tabela regressiva de IR.
Diretrizes Anti-Gambiarra: Validação determinística de matemática financeira e alíquotas oficiais.
"""
from wintoolbox.tools.calc.investments.logic import (
    calculate_fixed_income_yield,
    get_regressive_ir_rate,
    simulate_all_investments,
)


def test_regressive_ir_rate():
    assert get_regressive_ir_rate(90) == 22.5   # Até 180 dias
    assert get_regressive_ir_rate(180) == 22.5
    assert get_regressive_ir_rate(181) == 20.0  # 181 a 360
    assert get_regressive_ir_rate(360) == 20.0
    assert get_regressive_ir_rate(361) == 17.5  # 361 a 720
    assert get_regressive_ir_rate(720) == 17.5
    assert get_regressive_ir_rate(721) == 15.0  # Acima de 720


def test_fixed_income_yield():
    # R$ 10.000, 0 aporte, 12 meses (360 dias -> 20% IR), 10% a.a.
    res = calculate_fixed_income_yield(
        valor_inicial=10000.0,
        aporte_mensal=0.0,
        meses=12,
        taxa_anual_pct=10.0,
        isento_ir=False
    )
    assert res["total_investido"] == 10000.0
    assert res["saldo_bruto"] == 11000.0
    assert res["lucro_bruto"] == 1000.0
    assert res["aliquota_ir"] == 20.0
    assert res["valor_ir"] == 200.0  # 20% de 1000
    assert res["saldo_liquido"] == 10800.0
    assert res["lucro_liquido"] == 800.0


def test_simulate_all_investments():
    data = simulate_all_investments(
        valor_inicial=10000.0,
        aporte_mensal=500.0,
        meses=24,
        selic_anual_pct=10.75,
        cdb_pct_cdi=105.0,
        lci_pct_cdi=90.0
    )
    assert "poupanca" in data
    assert "cdb" in data
    assert "lci_lca" in data
    assert "tesouro_selic" in data

    # Em 24 meses (720 dias), taxa de IR do CDB é 17.5%
    assert data["cdb"]["aliquota_ir"] == 17.5
    assert data["lci_lca"]["isento"] is True
    assert data["poupanca"]["isento"] is True

    # Rendimento líquido do CDB e LCI deve ser superior à poupança
    assert data["cdb"]["saldo_liquido"] > data["poupanca"]["saldo_liquido"]
    assert data["lci_lca"]["saldo_liquido"] > data["poupanca"]["saldo_liquido"]
