"""
Lógica pura para estimativa de materiais de construção e reformas residenciais.
Inclui cálculo de tintas e embalagens ideais, revestimentos cerâmicos/porcelanato com perda,
argamassa, rejunte e volume de concreto/contrapiso.
Desacoplada de frameworks de interface gráfica.
"""
import math
from typing import Any, Dict, Tuple


def calculate_paint_materials(
    area_m2: float,
    num_demaos: int = 2,
    rendimento_m2_litro: float = 10.0
) -> Dict[str, Any]:
    """
    Calcula o volume total de tinta necessário e a melhor combinação de embalagens comerciais
    (Latas 18L, Galões 3.6L e Quartos 900ml).
    """
    if area_m2 <= 0 or num_demaos <= 0 or rendimento_m2_litro <= 0:
        return {
            "litros_totais": 0.0,
            "latas_18l": 0,
            "galoes_3_6l": 0,
            "quartos_0_9l": 0,
            "capacidade_total": 0.0,
            "sobra_litros": 0.0
        }

    litros_necessarios = (area_m2 * num_demaos) / rendimento_m2_litro

    # Otimização gulosa de latas
    rem = litros_necessarios
    latas_18 = int(rem // 18.0)
    rem = rem % 18.0

    galoes = int(rem // 3.6)
    rem = rem % 3.6

    quartos = math.ceil(rem / 0.9)

    # Otimização se 4 quartos completam 1 galão
    if quartos >= 4:
        galoes += 1
        quartos = 0

    if galoes >= 5:
        latas_18 += 1
        galoes = 0

    capacidade_total = round((latas_18 * 18.0) + (galoes * 3.6) + (quartos * 0.9), 2)
    sobra = max(0.0, round(capacidade_total - litros_necessarios, 2))

    return {
        "litros_totais": round(litros_necessarios, 2),
        "latas_18l": latas_18,
        "galoes_3_6l": galoes,
        "quartos_0_9l": quartos,
        "capacidade_total": capacidade_total,
        "sobra_litros": sobra
    }


def calculate_flooring_materials(
    area_m2: float,
    margem_perda_pct: float = 10.0,
    m2_por_caixa: float = 2.0,
    espessura_argamassa_kg_m2: float = 5.0,
    consumo_rejunte_kg_m2: float = 0.5
) -> Dict[str, Any]:
    """
    Calcula a quantidade de caixas de piso/porcelanato com percentual de corte e quebra,
    além de sacos de argamassa (20kg) e pacotes de rejunte (1kg).
    """
    if area_m2 <= 0:
        return {
            "area_liquida_m2": 0.0,
            "area_total_m2": 0.0,
            "caixas_necessarias": 0,
            "sacos_argamassa_20kg": 0,
            "kg_rejunte": 0.0
        }

    fator_perda = 1.0 + (margem_perda_pct / 100.0)
    area_total = round(area_m2 * fator_perda, 2)

    m2_cx = max(0.1, m2_por_caixa)
    caixas = math.ceil(area_total / m2_cx)

    # Argamassa (sacos de 20kg)
    total_argamassa_kg = area_total * espessura_argamassa_kg_m2
    sacos_argamassa = math.ceil(total_argamassa_kg / 20.0)

    # Rejunte
    total_rejunte_kg = round(area_total * consumo_rejunte_kg_m2, 2)

    return {
        "area_liquida_m2": round(area_m2, 2),
        "area_total_m2": area_total,
        "caixas_necessarias": caixas,
        "total_m2_comprado": round(caixas * m2_cx, 2),
        "sacos_argamassa_20kg": sacos_argamassa,
        "kg_rejunte": total_rejunte_kg
    }


def calculate_concrete_volume(
    area_m2: float,
    espessura_cm: float
) -> Dict[str, Any]:
    """
    Calcula volume de concreto/contrapiso em metros cúbicos (m³)
    e estimativa de insumos no traço convencional 1:2:3.
    """
    if area_m2 <= 0 or espessura_cm <= 0:
        return {"volume_m3": 0.0, "sacos_cimento_50kg": 0, "areia_m3": 0.0, "brita_m3": 0.0}

    espessura_m = espessura_cm / 100.0
    volume_m3 = round(area_m2 * espessura_m, 3)

    # Traço 1:2:3 consome em média 7 sacos de cimento de 50kg por m³ de concreto
    sacos_cimento = math.ceil(volume_m3 * 7.0)
    areia_m3 = round(volume_m3 * 0.65, 2)
    brita_m3 = round(volume_m3 * 0.85, 2)

    return {
        "volume_m3": volume_m3,
        "sacos_cimento_50kg": sacos_cimento,
        "areia_m3": areia_m3,
        "brita_m3": brita_m3
    }
