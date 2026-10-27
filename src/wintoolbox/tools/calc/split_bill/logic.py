"""
Lógica pura para divisão de contas de restaurantes, eventos e despesas compartilhadas.
Suporta divisão igualitária rápida e divisão individualizada com itens consumidos por subgrupos,
taxa de serviço (gorjeta) e couvert artístico.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


def calculate_quick_split(
    subtotal: float,
    num_pessoas: int,
    taxa_servico_pct: float = 10.0,
    couvert_por_pessoa: float = 0.0,
    desconto_reais: float = 0.0
) -> Dict[str, Any]:
    """
    Divisão igualitária simples de conta de mesa com taxa de serviço e couvert.
    """
    pessoas = max(1, num_pessoas)
    sub = max(0.0, subtotal - desconto_reais)
    taxa_servico = round(sub * (taxa_servico_pct / 100.0), 2)
    total_couvert = round(couvert_por_pessoa * pessoas, 2)
    total_geral = round(sub + taxa_servico + total_couvert, 2)
    valor_por_pessoa = round(total_geral / pessoas, 2)

    return {
        "subtotal": round(sub, 2),
        "taxa_servico": taxa_servico,
        "total_couvert": total_couvert,
        "total_geral": total_geral,
        "pessoas": pessoas,
        "valor_por_pessoa": valor_por_pessoa
    }


def calculate_itemized_split(
    participants: List[str],
    items: List[Tuple[str, float, List[str]]],
    taxa_servico_pct: float = 10.0,
    couvert_por_pessoa: float = 0.0
) -> Dict[str, Any]:
    """
    Divisão individualizada de despesas.
    items: Lista de (descricao, valor, consumidores). Se consumidores for vazio, divide entre todos os participantes.
    """
    if not participants:
        return {}

    p_totals = {p: 0.0 for p in participants}

    for desc, val, consumers in items:
        valid_consumers = [c for c in consumers if c in p_totals] if consumers else participants
        if not valid_consumers:
            valid_consumers = participants

        frac = val / len(valid_consumers)
        for c in valid_consumers:
            p_totals[c] += frac

    multiplicador_servico = 1.0 + (taxa_servico_pct / 100.0)

    breakdown = {}
    total_geral = 0.0

    for p, sub in p_totals.items():
        com_servico = sub * multiplicador_servico
        total_p = round(com_servico + couvert_por_pessoa, 2)
        breakdown[p] = {
            "consumo_subtotal": round(sub, 2),
            "taxa_servico": round(sub * (taxa_servico_pct / 100.0), 2),
            "couvert": round(couvert_por_pessoa, 2),
            "total_a_pagar": total_p
        }
        total_geral += total_p

    return {
        "participants_breakdown": breakdown,
        "total_geral": round(total_geral, 2),
        "participantes_count": len(participants)
    }
