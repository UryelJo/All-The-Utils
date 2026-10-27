"""
Lógica pura para simulação comparativa de investimentos de renda fixa brasileira.
Aplica a tabela regressiva de alíquotas do Imposto de Renda e calcula rendimento de Poupança,
CDBs (% do CDI), LCIs/LCAs (isentas de IR) e Tesouro Direto.
Desacoplada de frameworks de interface gráfica.
"""
from typing import Any, Dict, List, Optional


def get_regressive_ir_rate(dias_corridos: int) -> float:
    """
    Retorna a alíquota regressiva do Imposto de Renda para aplicações financeiras no Brasil.
    """
    if dias_corridos <= 180:
        return 22.5
    elif dias_corridos <= 360:
        return 20.0
    elif dias_corridos <= 720:
        return 17.5
    else:
        return 15.0


def calculate_fixed_income_yield(
    valor_inicial: float,
    aporte_mensal: float,
    meses: int,
    taxa_anual_pct: float,
    isento_ir: bool = False
) -> Dict[str, Any]:
    """
    Simula o rendimento composto de uma aplicação de renda fixa mês a mês,
    aplicando a alíquota de IR sobre o lucro no resgate.
    """
    if meses <= 0 or (valor_inicial <= 0 and aporte_mensal <= 0):
        return {
            "total_investido": 0.0,
            "saldo_bruto": 0.0,
            "lucro_bruto": 0.0,
            "aliquota_ir": 0.0,
            "valor_ir": 0.0,
            "saldo_liquido": 0.0,
            "lucro_liquido": 0.0,
            "rentabilidade_liquida_pct": 0.0
        }

    # Taxa mensal equivalente: (1 + i_ano)^(1/12) - 1
    i_ano = taxa_anual_pct / 100.0
    i_mes = ((1.0 + i_ano) ** (1.0 / 12.0)) - 1.0

    saldo = valor_inicial
    total_investido = valor_inicial

    for _ in range(meses):
        saldo = (saldo * (1.0 + i_mes)) + aporte_mensal
        total_investido += aporte_mensal

    lucro_bruto = max(0.0, saldo - total_investido)

    dias_corridos = meses * 30
    if isento_ir:
        aliquota_ir = 0.0
        valor_ir = 0.0
    else:
        aliquota_ir = get_regressive_ir_rate(dias_corridos)
        valor_ir = round(lucro_bruto * (aliquota_ir / 100.0), 2)

    saldo_liquido = round(saldo - valor_ir, 2)
    lucro_liquido = round(saldo_liquido - total_investido, 2)
    rentab_liq_pct = round((lucro_liquido / total_investido) * 100.0, 2) if total_investido > 0 else 0.0

    return {
        "total_investido": round(total_investido, 2),
        "saldo_bruto": round(saldo, 2),
        "lucro_bruto": round(lucro_bruto, 2),
        "aliquota_ir": aliquota_ir,
        "valor_ir": valor_ir,
        "saldo_liquido": saldo_liquido,
        "lucro_liquido": lucro_liquido,
        "rentabilidade_liquida_pct": rentab_liq_pct
    }


def simulate_all_investments(
    valor_inicial: float,
    aporte_mensal: float,
    meses: int,
    selic_anual_pct: float = 10.75,
    cdb_pct_cdi: float = 105.0,
    lci_pct_cdi: float = 90.0
) -> Dict[str, Dict[str, Any]]:
    """
    Compara lado a lado os principais ativos de renda fixa brasileira.
    """
    cdi_anual = max(0.0, selic_anual_pct - 0.10)

    # 1. Poupança: se Selic > 8.5% -> 6.17% a.a. + TR estimada (aprox. 6.8% a.a.)
    if selic_anual_pct > 8.5:
        taxa_poupanca = 6.80
    else:
        taxa_poupanca = round((selic_anual_pct * 0.70) + 0.5, 2)

    # 2. CDB
    taxa_cdb = round(cdi_anual * (cdb_pct_cdi / 100.0), 2)

    # 3. LCI / LCA (Isenta)
    taxa_lci = round(cdi_anual * (lci_pct_cdi / 100.0), 2)

    # 4. Tesouro Selic (100% Selic)
    taxa_tesouro = selic_anual_pct

    return {
        "poupanca": {
            "nome": "Caderneta de Poupança",
            "taxa_anual": taxa_poupanca,
            "isento": True,
            **calculate_fixed_income_yield(valor_inicial, aporte_mensal, meses, taxa_poupanca, isento_ir=True)
        },
        "cdb": {
            "nome": f"CDB ({cdb_pct_cdi:g}% do CDI)",
            "taxa_anual": taxa_cdb,
            "isento": False,
            **calculate_fixed_income_yield(valor_inicial, aporte_mensal, meses, taxa_cdb, isento_ir=False)
        },
        "lci_lca": {
            "nome": f"LCI / LCA ({lci_pct_cdi:g}% do CDI Isenta)",
            "taxa_anual": taxa_lci,
            "isento": True,
            **calculate_fixed_income_yield(valor_inicial, aporte_mensal, meses, taxa_lci, isento_ir=True)
        },
        "tesouro_selic": {
            "nome": "Tesouro Selic (100% Selic)",
            "taxa_anual": taxa_tesouro,
            "isento": False,
            **calculate_fixed_income_yield(valor_inicial, aporte_mensal, meses, taxa_tesouro, isento_ir=False)
        }
    }
