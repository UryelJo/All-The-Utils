"""
Lógica pura de matemática financeira: juros compostos, financiamento Price/SAC e margens.
Totalmente isolada de bibliotecas gráficas.
"""
import math
from typing import Any, Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("calc.finance")


def calculate_compound_interest(
    initial_amount: float,
    monthly_deposit: float,
    annual_rate_percent: float,
    total_months: int
) -> Dict[str, Any]:
    """
    Calcula juros compostos com aportes mensais.
    A taxa anual é convertida para taxa mensal equivalente: (1 + i_a)^(1/12) - 1.
    """
    p = max(0.0, float(initial_amount))
    pmt = max(0.0, float(monthly_deposit))
    months = max(1, int(total_months))

    # Taxa mensal equivalente
    annual_rate = max(0.0, annual_rate_percent) / 100.0
    monthly_rate = math.pow(1.0 + annual_rate, 1.0 / 12.0) - 1.0

    current_balance = p
    total_invested = p
    history_by_year: List[Dict[str, Any]] = []

    for m in range(1, months + 1):
        # Rende sobre o saldo
        interest = current_balance * monthly_rate
        current_balance += interest + pmt
        total_invested += pmt

        # Registra marcos anuais ou o último mês
        if m % 12 == 0 or m == months:
            year_num = (m + 11) // 12
            history_by_year.append({
                "month": m,
                "year": year_num,
                "invested": round(total_invested, 2),
                "total_interest": round(current_balance - total_invested, 2),
                "balance": round(current_balance, 2)
            })

    total_interest = max(0.0, current_balance - total_invested)

    return {
        "initial_amount": round(p, 2),
        "monthly_deposit": round(pmt, 2),
        "total_invested": round(total_invested, 2),
        "total_interest": round(total_interest, 2),
        "final_balance": round(current_balance, 2),
        "annual_rate": annual_rate_percent,
        "monthly_rate_percent": round(monthly_rate * 100.0, 4),
        "total_months": months,
        "history": history_by_year
    }


def calculate_financing(
    loan_amount: float,
    annual_interest_rate: float,
    total_months: int,
    system: str = "PRICE"  # "PRICE" ou "SAC"
) -> Dict[str, Any]:
    """
    Simula financiamento imobiliário ou veicular nos sistemas Price ou SAC.
    """
    pv = max(0.0, float(loan_amount))
    months = max(1, int(total_months))
    annual_rate = max(0.0, annual_interest_rate) / 100.0
    i = annual_rate / 12.0  # Taxa mensal proporcional padrão bancário

    if pv <= 0:
        return {"error": "O valor financiado deve ser maior que zero."}

    schedule: List[Dict[str, Any]] = []
    total_paid = 0.0
    total_interest = 0.0

    if system.upper() == "PRICE":
        # Tabela Price: parcelas fixas PMT = PV * [i * (1+i)^n] / [(1+i)^n - 1]
        if i > 0:
            factor = math.pow(1.0 + i, months)
            pmt = pv * (i * factor) / (factor - 1.0)
        else:
            pmt = pv / months

        balance = pv
        for m in range(1, months + 1):
            interest_month = balance * i
            amortization = pmt - interest_month
            balance -= amortization
            if balance < 0:
                balance = 0.0

            total_paid += pmt
            total_interest += interest_month

            if m <= 5 or m == months or m % 12 == 0:
                schedule.append({
                    "month": m,
                    "payment": round(pmt, 2),
                    "amortization": round(amortization, 2),
                    "interest": round(interest_month, 2),
                    "balance": round(balance, 2)
                })

        first_pmt = pmt
        last_pmt = pmt

    else:
        # Tabela SAC: amortização constante A = PV / n
        amortization = pv / months
        balance = pv
        first_pmt = 0.0
        last_pmt = 0.0

        for m in range(1, months + 1):
            interest_month = balance * i
            pmt = amortization + interest_month
            balance -= amortization
            if balance < 0:
                balance = 0.0

            if m == 1:
                first_pmt = pmt
            if m == months:
                last_pmt = pmt

            total_paid += pmt
            total_interest += interest_month

            if m <= 5 or m == months or m % 12 == 0:
                schedule.append({
                    "month": m,
                    "payment": round(pmt, 2),
                    "amortization": round(amortization, 2),
                    "interest": round(interest_month, 2),
                    "balance": round(balance, 2)
                })

    return {
        "system": system.upper(),
        "loan_amount": round(pv, 2),
        "total_months": months,
        "first_payment": round(first_pmt, 2),
        "last_payment": round(last_pmt, 2),
        "total_paid": round(total_paid, 2),
        "total_interest": round(total_interest, 2),
        "schedule": schedule
    }


def calculate_margin_and_markup(cost_price: float, sell_price: float) -> Dict[str, float]:
    """Calcula margem líquida e markup a partir do preço de custo e venda."""
    cost = max(0.0, cost_price)
    sell = max(0.0, sell_price)
    profit = sell - cost

    markup = (profit / cost * 100.0) if cost > 0 else 0.0
    margin = (profit / sell * 100.0) if sell > 0 else 0.0

    return {
        "cost": round(cost, 2),
        "sell": round(sell, 2),
        "profit": round(profit, 2),
        "markup_percent": round(markup, 2),
        "margin_percent": round(margin, 2)
    }
