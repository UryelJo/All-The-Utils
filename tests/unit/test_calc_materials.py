"""
Testes unitários para a calculadora de materiais de construção e reformas.
Diretrizes Anti-Gambiarra: Validação determinística de cálculos de insumos e embalagens.
"""
from wintoolbox.tools.calc.materials.logic import (
    calculate_concrete_volume,
    calculate_flooring_materials,
    calculate_paint_materials,
)


def test_calculate_paint_materials():
    # 90 m², 2 demãos, rendimento 10 m²/L -> 18 Litros
    # Deve dar exatamente 1 lata de 18L e 0 sobras
    p1 = calculate_paint_materials(area_m2=90.0, num_demaos=2, rendimento_m2_litro=10.0)
    assert p1["litros_totais"] == 18.0
    assert p1["latas_18l"] == 1
    assert p1["galoes_3_6l"] == 0
    assert p1["quartos_0_9l"] == 0
    assert p1["sobra_litros"] == 0.0

    # 36 m², 1 demão, rendimento 10 m²/L -> 3.6 Litros -> 1 galão de 3.6L
    p2 = calculate_paint_materials(area_m2=36.0, num_demaos=1, rendimento_m2_litro=10.0)
    assert p2["litros_totais"] == 3.6
    assert p2["latas_18l"] == 0
    assert p2["galoes_3_6l"] == 1


def test_calculate_flooring_materials():
    # 20 m², 10% perda -> 22 m²
    # 2.0 m²/caixa -> 11 caixas
    f = calculate_flooring_materials(area_m2=20.0, margem_perda_pct=10.0, m2_por_caixa=2.0)
    assert f["area_liquida_m2"] == 20.0
    assert f["area_total_m2"] == 22.0
    assert f["caixas_necessarias"] == 11
    assert f["total_m2_comprado"] == 22.0
    assert f["sacos_argamassa_20kg"] == 6  # 22 * 5 = 110 kg / 20 = 5.5 -> 6 sacos
    assert f["kg_rejunte"] == 11.0          # 22 * 0.5 = 11.0 kg


def test_calculate_concrete_volume():
    # 10 m², 10 cm espessura -> 1.0 m³
    c = calculate_concrete_volume(area_m2=10.0, espessura_cm=10.0)
    assert c["volume_m3"] == 1.0
    assert c["sacos_cimento_50kg"] == 7
    assert c["areia_m3"] == 0.65
    assert c["brita_m3"] == 0.85
