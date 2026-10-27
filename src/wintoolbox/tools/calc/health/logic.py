"""
Lógica pura para cálculos biométricos de saúde, metabolismo e hidratação.
Inclui IMC (OMS), Taxa Metabólica Basal (Mifflin-St Jeor e Harris-Benedict),
Gasto Calórico Total Diário (TDEE) e ingestão de água recomendada.
Desacoplada de frameworks de interface gráfica.
"""
from typing import Any, Dict, Tuple


def calculate_imc(peso_kg: float, altura_cm: float) -> Tuple[float, str, str]:
    """
    Calcula o Índice de Massa Corporal (IMC) e a classificação oficial segundo a OMS.
    Retorna: (imc_arredondado, classificacao, faixa_peso_ideal).
    """
    if peso_kg <= 0 or altura_cm <= 0:
        return 0.0, "Dados Inválidos", "0 - 0 kg"

    altura_m = altura_cm / 100.0
    imc = round(peso_kg / (altura_m ** 2), 2)

    if imc < 18.5:
        classificacao = "Abaixo do peso"
    elif imc <= 24.9:
        classificacao = "Peso normal"
    elif imc <= 29.9:
        classificacao = "Sobrepeso"
    elif imc <= 34.9:
        classificacao = "Obesidade Grau I"
    elif imc <= 39.9:
        classificacao = "Obesidade Grau II"
    else:
        classificacao = "Obesidade Grau III (Mórbida)"

    peso_ideal_min = round(18.5 * (altura_m ** 2), 1)
    peso_ideal_max = round(24.9 * (altura_m ** 2), 1)
    peso_ideal_str = f"{peso_ideal_min:.1f} kg a {peso_ideal_max:.1f} kg"

    return imc, classificacao, peso_ideal_str


def calculate_tmb_mifflin_st_jeor(peso_kg: float, altura_cm: float, idade: int, sexo: str = "M") -> float:
    """
    Calcula a Taxa Metabólica Basal (TMB) pelo método moderno de Mifflin-St Jeor.
    sexo: 'M' para Masculino, 'F' para Feminino.
    """
    if peso_kg <= 0 or altura_cm <= 0 or idade <= 0:
        return 0.0

    base = (10.0 * peso_kg) + (6.25 * altura_cm) - (5.0 * idade)
    if sexo.upper() == "M":
        return round(base + 5.0, 1)
    else:
        return round(base - 161.0, 1)


def calculate_tmb_harris_benedict(peso_kg: float, altura_cm: float, idade: int, sexo: str = "M") -> float:
    """
    Calcula a TMB pelo método clássico de Harris-Benedict.
    """
    if peso_kg <= 0 or altura_cm <= 0 or idade <= 0:
        return 0.0

    if sexo.upper() == "M":
        tmb = 66.5 + (13.75 * peso_kg) + (5.003 * altura_cm) - (6.75 * idade)
    else:
        tmb = 655.1 + (9.563 * peso_kg) + (1.850 * altura_cm) - (4.676 * idade)

    return round(tmb, 1)


ATIVIDADE_FATORES = {
    "sedentario": 1.2,           # Pouco ou nenhum exercício
    "leve": 1.375,               # Exercício leve 1 a 3 dias/semana
    "moderado": 1.55,            # Exercício moderado 3 a 5 dias/semana
    "intenso": 1.725,            # Exercício pesado 6 a 7 dias/semana
    "extremo": 1.9,              # Exercício muito intenso ou trabalho físico pesado
}


def calculate_tdee_and_goals(tmb: float, nivel_atividade: str = "moderado") -> Dict[str, float]:
    """
    Calcula o Gasto Energético Total Diário (TDEE) e metas calóricas para objetivos específicos.
    """
    fator = ATIVIDADE_FATORES.get(nivel_atividade.lower(), 1.55)
    tdee = round(tmb * fator, 1)

    return {
        "tdee_manutencao": tdee,
        "emagrecimento_leve": max(1000.0, round(tdee - 300.0, 1)),
        "emagrecimento_moderado": max(1000.0, round(tdee - 500.0, 1)),
        "hipertrofia_ganho": round(tdee + 350.0, 1)
    }


def calculate_water_intake(peso_kg: float, exercicio_minutos: int = 0) -> Dict[str, Any]:
    """
    Calcula a ingestão diária recomendada de água com base no peso e atividade.
    Regra padrão: 35 ml/kg + acréscimo de 500 ml para cada 45 min de treino.
    """
    if peso_kg <= 0:
        return {"total_ml": 0, "total_litros": 0.0, "copos_250ml": 0}

    base_ml = peso_kg * 35.0
    extra_ml = (exercicio_minutos / 45.0) * 500.0
    total_ml = int(round(base_ml + extra_ml))
    total_l = round(total_ml / 1000.0, 2)
    copos = int(round(total_ml / 250.0))

    return {
        "total_ml": total_ml,
        "total_litros": total_l,
        "copos_250ml": copos
    }
