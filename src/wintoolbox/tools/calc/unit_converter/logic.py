"""
Lógica pura de conversão de unidades físicas, digitais e dimensionais.
Zero acoplamento com bibliotecas visuais ou externas.
"""
from typing import Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("calc.unit_converter")

# Dicionário de categorias e seus fatores em relação a uma unidade base
UNIT_DEFINITIONS: Dict[str, Dict[str, float]] = {
    "Comprimento": {
        "Metro (m)": 1.0,
        "Quilômetro (km)": 1000.0,
        "Centímetro (cm)": 0.01,
        "Milímetro (mm)": 0.001,
        "Micrômetro (µm)": 1e-6,
        "Nanômetro (nm)": 1e-9,
        "Polegada (in)": 0.0254,
        "Pé (ft)": 0.3048,
        "Jarda (yd)": 0.9144,
        "Milha (mi)": 1609.344,
        "Milha Náutica (NM)": 1852.0
    },
    "Massa e Peso": {
        "Quilograma (kg)": 1.0,
        "Grama (g)": 0.001,
        "Miligrama (mg)": 1e-6,
        "Tonelada Métrica (t)": 1000.0,
        "Libra (lb)": 0.45359237,
        "Onça (oz)": 0.028349523125,
        "Arroba (Brasil)": 15.0
    },
    "Dados Digitais": {
        "Byte (B)": 1.0,
        "Bit (b)": 0.125,
        "Kilobyte (KB - 1000 B)": 1000.0,
        "Megabyte (MB - 1000 KB)": 1e6,
        "Gigabyte (GB - 1000 MB)": 1e9,
        "Terabyte (TB - 1000 GB)": 1e12,
        "Petabyte (PB)": 1e15,
        "Kibibyte (KiB - 1024 B)": 1024.0,
        "Mebibyte (MiB - 1024 KiB)": 1048576.0,
        "Gibibyte (GiB - 1024 MiB)": 1073741824.0,
        "Tebibyte (TiB - 1024 GiB)": 1099511627776.0
    },
    "Área": {
        "Metro Quadrado (m²)": 1.0,
        "Quilômetro Quadrado (km²)": 1e6,
        "Centímetro Quadrado (cm²)": 1e-4,
        "Hectare (ha)": 10000.0,
        "Acre": 4046.8564224,
        "Pé Quadrado (ft²)": 0.09290304,
        "Alqueire Paulista (24.200 m²)": 24200.0
    },
    "Volume": {
        "Litro (L)": 1.0,
        "Mililitro (mL)": 0.001,
        "Metro Cúbico (m³)": 1000.0,
        "Centímetro Cúbico (cm³ / cc)": 0.001,
        "Galão Americano (gal)": 3.785411784,
        "Quarto Americano (qt)": 0.946352946,
        "Pinta Americana (pt)": 0.473176473,
        "Xícara (240 mL)": 0.24,
        "Colher de Sopa (15 mL)": 0.015,
        "Colher de Chá (5 mL)": 0.005
    },
    "Velocidade": {
        "Quilômetros por Hora (km/h)": 1.0,
        "Metros por Segundo (m/s)": 3.6,
        "Milhas por Hora (mph)": 1.609344,
        "Nós Náuticos (kt)": 1.852,
        "Velocidade do Som (Mach)": 1234.8
    },
    "Pressão": {
        "Bar (bar)": 1.0,
        "Pascal (Pa)": 1e-5,
        "Quilopascal (kPa)": 0.01,
        "Atmosfera Padrão (atm)": 1.01325,
        "Libras por Pol² (psi)": 0.0689475729,
        "Milímetros de Mercúrio (mmHg)": 0.00133322387
    },
    "Tempo": {
        "Segundo (s)": 1.0,
        "Milissegundo (ms)": 0.001,
        "Minuto (min)": 60.0,
        "Hora (h)": 3600.0,
        "Dia (d)": 86400.0,
        "Semana": 604800.0,
        "Ano Comum (365 d)": 31536000.0
    }
}


def get_categories() -> List[str]:
    """Retorna lista de categorias de conversão disponíveis."""
    return list(UNIT_DEFINITIONS.keys()) + ["Temperatura"]


def get_units_for_category(category: str) -> List[str]:
    """Retorna a lista de unidades suportadas na categoria."""
    if category == "Temperatura":
        return ["Celsius (°C)", "Fahrenheit (°F)", "Kelvin (K)"]
    return list(UNIT_DEFINITIONS.get(category, {}).keys())


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Conversão especial de escalas termométricas."""
    # 1. Converte de origem para Celsius
    if "Celsius" in from_unit:
        celsius = value
    elif "Fahrenheit" in from_unit:
        celsius = (value - 32.0) * 5.0 / 9.0
    elif "Kelvin" in from_unit:
        celsius = value - 273.15
    else:
        celsius = value

    # 2. Converte de Celsius para destino
    if "Celsius" in to_unit:
        return celsius
    elif "Fahrenheit" in to_unit:
        return (celsius * 9.0 / 5.0) + 32.0
    elif "Kelvin" in to_unit:
        return celsius + 273.15
    return celsius


def convert_units(
    value: float,
    category: str,
    from_unit: str,
    to_unit: str
) -> float:
    """Realiza a conversão de valor entre unidades da mesma categoria."""
    if from_unit == to_unit:
        return value

    if category == "Temperatura":
        return convert_temperature(value, from_unit, to_unit)

    cat_dict = UNIT_DEFINITIONS.get(category)
    if not cat_dict or from_unit not in cat_dict or to_unit not in cat_dict:
        raise ValueError(f"Unidade inválida para categoria {category}: {from_unit} -> {to_unit}")

    # Converte para base e depois para destino
    val_in_base = value * cat_dict[from_unit]
    result = val_in_base / cat_dict[to_unit]
    return result


def get_all_conversions_in_category(value: float, category: str, from_unit: str) -> List[Tuple[str, float]]:
    """Gera tabela completa de conversão para todas as unidades da categoria."""
    units = get_units_for_category(category)
    results = []
    for u in units:
        conv_val = convert_units(value, category, from_unit, u)
        results.append((u, conv_val))
    return results
