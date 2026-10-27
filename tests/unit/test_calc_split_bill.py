"""
Testes unitários para a calculadora de divisão de contas e rateio de despesas.
Diretrizes Anti-Gambiarra: Validação determinística de rateio e conservação da soma total.
"""
from wintoolbox.tools.calc.split_bill.logic import (
    calculate_itemized_split,
    calculate_quick_split,
)


def test_quick_split():
    # Subtotal: R$ 200,00, 4 pessoas, taxa 10% (R$ 20,00), couvert R$ 5,00/pessoa (R$ 20,00)
    # Total Geral = 200 + 20 + 20 = 240,00 -> R$ 60,00 por pessoa
    res = calculate_quick_split(
        subtotal=200.0,
        num_pessoas=4,
        taxa_servico_pct=10.0,
        couvert_por_pessoa=5.0
    )
    assert res["subtotal"] == 200.0
    assert res["taxa_servico"] == 20.0
    assert res["total_couvert"] == 20.0
    assert res["total_geral"] == 240.0
    assert res["valor_por_pessoa"] == 60.0


def test_itemized_split():
    participants = ["Carlos", "Ana"]
    items = [
        ("Pizza", 60.0, ["Carlos", "Ana"]),  # 30 cada
        ("Cerveja", 20.0, ["Carlos"]),        # 20 Carlos
        ("Suco", 10.0, ["Ana"]),             # 10 Ana
    ]
    # Carlos sub = 30 + 20 = 50. Com 10% = 55.00
    # Ana sub = 30 + 10 = 40. Com 10% = 44.00
    # Total = 99.00
    res = calculate_itemized_split(
        participants=participants,
        items=items,
        taxa_servico_pct=10.0,
        couvert_por_pessoa=0.0
    )
    bk = res["participants_breakdown"]
    assert bk["Carlos"]["consumo_subtotal"] == 50.0
    assert bk["Carlos"]["total_a_pagar"] == 55.0
    assert bk["Ana"]["consumo_subtotal"] == 40.0
    assert bk["Ana"]["total_a_pagar"] == 44.0
    assert res["total_geral"] == 99.0
