"""
Testes unitários rigorosos para a Calculadora Financeira (calc.finance).
"""
import pytest
from PySide6.QtWidgets import QApplication

from wintoolbox.tools.calc.finance.logic import (
    calculate_compound_interest,
    calculate_financing,
    calculate_margin_and_markup
)
from wintoolbox.tools.calc.finance.tool import FinanceTool, FinanceView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_compound_interest_calculation():
    """Valida cálculo de juros compostos com e sem aportes."""
    # Cenário 1: R$ 10.000 a 10% a.a. por 12 meses sem aportes mensais
    # A taxa mensal equivalente (1 + 0.10)^(1/12) - 1 rende exatamente 10% ao final do 12º mês
    res = calculate_compound_interest(
        initial_amount=10000.0,
        monthly_deposit=0.0,
        annual_rate_percent=10.0,
        total_months=12
    )
    assert res["initial_amount"] == 10000.0
    assert res["total_invested"] == 10000.0
    assert res["final_balance"] == 11000.0
    assert res["total_interest"] == 1000.0
    assert len(res["history"]) == 1
    assert res["history"][0]["year"] == 1
    assert res["history"][0]["balance"] == 11000.0

    # Cenário 2: R$ 1.000 inicial, R$ 100 mensais por 24 meses a 0%
    res_zero = calculate_compound_interest(1000.0, 100.0, 0.0, 24)
    assert res_zero["total_invested"] == 3400.0
    assert res_zero["final_balance"] == 3400.0
    assert res_zero["total_interest"] == 0.0


def test_financing_price_and_sac():
    """Valida simulações de financiamento bancário nos sistemas Price e SAC."""
    loan = 120000.0
    annual_rate = 12.0  # 1% ao mês proporcional
    months = 12

    # 1. Tabela SAC: Amortização constante = 120.000 / 12 = 10.000 / mês
    sac = calculate_financing(loan, annual_rate, months, system="SAC")
    assert sac["system"] == "SAC"
    assert sac["loan_amount"] == 120000.0
    assert sac["total_months"] == 12
    # Primeira parcela: Amortização (10.000) + Juros sobre 120.000 (1.200) = 11.200
    assert sac["first_payment"] == 11200.0
    # Última parcela: Amortização (10.000) + Juros sobre 10.000 (100) = 10.100
    assert sac["last_payment"] == 10100.0
    # Total de juros SAC = 1.200 + 1.100 + ... + 100 = 7.800
    assert sac["total_interest"] == 7800.0
    assert sac["total_paid"] == 127800.0

    # 2. Tabela Price: Parcelas fixas
    price = calculate_financing(loan, annual_rate, months, system="PRICE")
    assert price["system"] == "PRICE"
    assert price["first_payment"] == price["last_payment"]
    # PMT para 120.000 a 1% a.m. por 12 meses: 120000 * 0.01 * (1.01^12) / (1.01^12 - 1) ~= 10661.85
    assert round(price["first_payment"], 2) == 10661.85
    assert round(price["total_paid"], 2) == 127942.26
    assert round(price["total_interest"], 2) == 7942.26

    # Erro com valor zerado
    err = calculate_financing(0.0, 10.0, 12, "PRICE")
    assert "error" in err


def test_margin_and_markup():
    """Valida cálculos comerciais de margem de lucro e markup."""
    # Custo: 100, Venda: 150 -> Lucro: 50, Markup: 50%, Margem: 33.33%
    res = calculate_margin_and_markup(100.0, 150.0)
    assert res["cost"] == 100.0
    assert res["sell"] == 150.0
    assert res["profit"] == 50.0
    assert res["markup_percent"] == 50.0
    assert res["margin_percent"] == 33.33

    # Custo zero
    zero_cost = calculate_margin_and_markup(0.0, 100.0)
    assert zero_cost["profit"] == 100.0
    assert zero_cost["markup_percent"] == 0.0
    assert zero_cost["margin_percent"] == 100.0


def test_finance_view(qapp):
    """Valida comportamento e rendering da interface gráfica da calculadora financeira."""
    tool = FinanceTool()
    view = FinanceView(tool)

    # 1. Aba Juros Compostos
    view.spin_initial.setValue(10000.0)
    view.spin_monthly.setValue(0.0)
    view.spin_rate.setValue(10.0)
    view.spin_years.setValue(1)
    view._calculate_compound()

    assert "10.000,00" in view.lbl_comp_invested.text()
    assert "1.000,00" in view.lbl_comp_interest.text()
    assert "11.000,00" in view.lbl_comp_final.text()
    assert view.table_compound.rowCount() == 1

    # 2. Aba Financiamento SAC
    view.spin_fin_amount.setValue(120000.0)
    view.spin_fin_rate.setValue(12.0)
    view.spin_fin_months.setValue(12)
    idx_sac = view.combo_fin_sys.findData("SAC")
    assert idx_sac >= 0
    view.combo_fin_sys.setCurrentIndex(idx_sac)
    view._calculate_financing()

    assert "11.200,00" in view.lbl_fin_first.text()
    assert "10.100,00" in view.lbl_fin_last.text()
    assert "127.800,00" in view.lbl_fin_total.text()

    # 3. Aba Margem e Markup
    view.spin_cost.setValue(100.0)
    view.spin_sell.setValue(150.0)
    view._calculate_margin()

    assert "50,00" in view.lbl_margin_profit.text()
    assert "33.33%" in view.lbl_margin_pct.text()
    assert "50.00%" in view.lbl_markup_pct.text()
