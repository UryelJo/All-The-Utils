"""
Lógica pura para cálculos da folha de pagamento e encargos trabalhistas no padrão CLT brasileiro.
Calcula INSS progressivo, IRRF com dependentes ou dedução simplificada, FGTS, férias com 1/3 e rescisão.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


# Tabelas oficiais de referência CLT (INSS progressivo e IRRF)
INSS_FAIXAS = [
    (1412.00, 0.075),
    (2666.68, 0.090),
    (4000.03, 0.120),
    (7786.02, 0.140),
]

DEDUCAO_DEPENDENTE_IRRF = 189.59
DESCONTO_SIMPLIFICADO_IRRF = 564.80

IRRF_FAIXAS = [
    (2259.20, 0.000, 0.00),
    (2826.65, 0.075, 169.44),
    (3751.05, 0.150, 381.44),
    (4664.68, 0.225, 662.77),
    (float("inf"), 0.275, 896.00),
]


def calculate_inss_progressive(salario_bruto: float) -> Tuple[float, float]:
    """
    Calcula o desconto de INSS progressivo por faixas salariais.
    Retorna: (valor_desconto_inss, aliquota_efetiva_percentual).
    """
    if salario_bruto <= 0:
        return 0.0, 0.0

    inss_total = 0.0
    faixa_anterior = 0.0

    for limite, aliquota in INSS_FAIXAS:
        if salario_bruto > limite:
            base_faixa = limite - faixa_anterior
            inss_total += base_faixa * aliquota
            faixa_anterior = limite
        else:
            base_faixa = salario_bruto - faixa_anterior
            inss_total += base_faixa * aliquota
            break

    inss_total = round(inss_total, 2)
    aliquota_efetiva = round((inss_total / salario_bruto) * 100, 2)
    return inss_total, aliquota_efetiva


def calculate_irrf(base_calculo: float, dependentes: int = 0, outras_deducoes: float = 0.0) -> Tuple[float, float, str]:
    """
    Calcula o IRRF comparando deduções legais (dependentes + outras) vs dedução simplificada.
    Retorna: (valor_irrf, aliquota_efetiva_percentual, tipo_metodo).
    """
    if base_calculo <= 0:
        return 0.0, 0.0, "Isento"

    deducao_dependentes = dependentes * DEDUCAO_DEPENDENTE_IRRF
    base_legal = max(0.0, base_calculo - deducao_dependentes - outras_deducoes)
    base_simplificada = max(0.0, base_calculo - DESCONTO_SIMPLIFICADO_IRRF)

    def _calc_tabela(base: float) -> float:
        for limite, aliq, deducao in IRRF_FAIXAS:
            if base <= limite:
                return max(0.0, round(base * aliq - deducao, 2))
        return 0.0

    irrf_legal = _calc_tabela(base_legal)
    irrf_simplificado = _calc_tabela(base_simplificada)

    if irrf_legal <= irrf_simplificado:
        irrf_escolhido = irrf_legal
        metodo = "Deduções Legais"
    else:
        irrf_escolhido = irrf_simplificado
        metodo = "Desconto Simplificado"

    aliq_efetiva = round((irrf_escolhido / base_calculo) * 100, 2) if base_calculo > 0 else 0.0
    return irrf_escolhido, aliq_efetiva, metodo


def calculate_folha_pagamento(
    salario_bruto: float,
    dependentes: int = 0,
    outros_descontos: float = 0.0,
    outros_proventos: float = 0.0,
    pensao_alimenticia: float = 0.0
) -> Dict[str, Any]:
    """
    Cálculo consolidado do contracheque / folha de pagamento CLT.
    """
    inss, aliq_inss = calculate_inss_progressive(salario_bruto)
    base_irrf = max(0.0, salario_bruto - inss - pensao_alimenticia)
    irrf, aliq_irrf, metodo_irrf = calculate_irrf(base_irrf, dependentes, outras_deducoes=0.0)

    fgts = round(salario_bruto * 0.08, 2)
    total_descontos = round(inss + irrf + pensao_alimenticia + outros_descontos, 2)
    salario_liquido = round(salario_bruto + outros_proventos - total_descontos, 2)

    return {
        "salario_bruto": round(salario_bruto, 2),
        "inss": inss,
        "aliq_inss": aliq_inss,
        "base_irrf": round(base_irrf, 2),
        "irrf": irrf,
        "aliq_irrf": aliq_irrf,
        "metodo_irrf": metodo_irrf,
        "fgts": fgts,
        "outros_descontos": round(outros_descontos, 2),
        "outros_proventos": round(outros_proventos, 2),
        "total_descontos": total_descontos,
        "salario_liquido": salario_liquido,
    }


def calculate_ferias(
    salario_bruto: float,
    dias_ferias: int = 30,
    abono_pecuniario_dias: int = 0,
    dependentes: int = 0
) -> Dict[str, Any]:
    """
    Calcula remuneração de férias com terço constitucional (1/3) e opção de abono pecuniário (venda de dias).
    """
    valor_dia = salario_bruto / 30.0
    valor_gozo = valor_dia * dias_ferias
    terco_gozo = valor_gozo / 3.0

    # Abono pecuniário (venda de até 10 dias) é isento de INSS e IRRF
    valor_abono = valor_dia * abono_pecuniario_dias
    terco_abono = valor_abono / 3.0
    total_abono = valor_abono + terco_abono

    base_tributavel = valor_gozo + terco_gozo
    inss, _ = calculate_inss_progressive(base_tributavel)
    base_irrf = max(0.0, base_tributavel - inss)
    irrf, _, _ = calculate_irrf(base_irrf, dependentes=dependentes)

    total_bruto = round(base_tributavel + total_abono, 2)
    total_descontos = round(inss + irrf, 2)
    total_liquido = round(total_bruto - total_descontos, 2)

    return {
        "valor_gozo": round(valor_gozo, 2),
        "terco_constitucional": round(terco_gozo, 2),
        "total_abono": round(total_abono, 2),
        "base_tributavel": round(base_tributavel, 2),
        "inss": inss,
        "irrf": irrf,
        "total_bruto": total_bruto,
        "total_descontos": total_descontos,
        "total_liquido": total_liquido
    }


def calculate_rescisao(
    salario_bruto: float,
    meses_trabalhados: int,
    tipo_motivo: str = "sem_justa_causa",  # 'sem_justa_causa', 'pedido_demissao', 'com_justa_causa', 'acordo_mutuo'
    saldo_salario_dias: int = 0,
    ferias_vencidas: bool = False,
    aviso_previo_indenizado: bool = True
) -> Dict[str, Any]:
    """
    Simula verbas rescisórias conforme o motivo de desligamento.
    """
    valor_dia = salario_bruto / 30.0
    saldo_salario = valor_dia * saldo_salario_dias

    # Proporções de 13º e Férias no ano corrente (meses / 12)
    fracao = min(12, max(0, meses_trabalhados % 12 or (12 if meses_trabalhados >= 12 else meses_trabalhados)))
    decimo_terceiro_prop = (salario_bruto / 12.0) * fracao
    ferias_prop = (salario_bruto / 12.0) * fracao
    terco_ferias_prop = ferias_prop / 3.0

    ferias_vencidas_val = (salario_bruto + (salario_bruto / 3.0)) if ferias_vencidas else 0.0

    aviso_previo = salario_bruto if (aviso_previo_indenizado and tipo_motivo == "sem_justa_causa") else 0.0

    multa_fgts = 0.0
    estimativa_saldo_fgts = (salario_bruto * 0.08) * meses_trabalhados
    if tipo_motivo == "sem_justa_causa":
        multa_fgts = estimativa_saldo_fgts * 0.40  # 40% de multa
    elif tipo_motivo == "acordo_mutuo":
        multa_fgts = estimativa_saldo_fgts * 0.20  # 20% no acordo da Reforma Trabalhista
        aviso_previo /= 2.0

    if tipo_motivo == "com_justa_causa":
        decimo_terceiro_prop = 0.0
        ferias_prop = 0.0
        terco_ferias_prop = 0.0
        aviso_previo = 0.0
        multa_fgts = 0.0

    total_bruto = round(
        saldo_salario + decimo_terceiro_prop + ferias_prop + terco_ferias_prop +
        ferias_vencidas_val + aviso_previo + multa_fgts,
        2
    )

    inss_saldo, _ = calculate_inss_progressive(saldo_salario)
    total_liquido = round(total_bruto - inss_saldo, 2)

    return {
        "tipo_motivo": tipo_motivo,
        "saldo_salario": round(saldo_salario, 2),
        "decimo_terceiro_prop": round(decimo_terceiro_prop, 2),
        "ferias_prop": round(ferias_prop, 2),
        "terco_ferias_prop": round(terco_ferias_prop, 2),
        "ferias_vencidas": round(ferias_vencidas_val, 2),
        "aviso_previo": round(aviso_previo, 2),
        "multa_fgts": round(multa_fgts, 2),
        "desconto_inss": inss_saldo,
        "total_bruto": total_bruto,
        "total_liquido": total_liquido
    }
