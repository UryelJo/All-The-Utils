"""
Testes unitários rigorosos para o Conversor de Unidades (calc.unit_converter).
"""
import pytest
from PySide6.QtWidgets import QApplication

from wintoolbox.tools.calc.unit_converter.logic import (
    convert_units,
    convert_temperature,
    get_categories,
    get_units_for_category,
    get_all_conversions_in_category
)
from wintoolbox.tools.calc.unit_converter.tool import UnitConverterTool, UnitConverterView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_unit_converter_categories_and_units():
    """Valida disponibilidade de categorias e unidades padrão."""
    cats = get_categories()
    assert "Comprimento" in cats
    assert "Massa e Peso" in cats
    assert "Dados Digitais" in cats
    assert "Temperatura" in cats

    temp_units = get_units_for_category("Temperatura")
    assert "Celsius (°C)" in temp_units
    assert "Fahrenheit (°F)" in temp_units
    assert "Kelvin (K)" in temp_units

    data_units = get_units_for_category("Dados Digitais")
    assert "Byte (B)" in data_units
    assert "Kibibyte (KiB - 1024 B)" in data_units
    assert "Gibibyte (GiB - 1024 MiB)" in data_units


def test_unit_converter_length_and_mass():
    """Valida cálculos exatos de comprimento e massa."""
    # 1. Metro para Quilômetro
    assert convert_units(1000.0, "Comprimento", "Metro (m)", "Quilômetro (km)") == 1.0
    # 2. Quilômetro para Metro
    assert convert_units(5.5, "Comprimento", "Quilômetro (km)", "Metro (m)") == 5500.0
    # 3. Polegada para Centímetro
    res_cm = convert_units(10.0, "Comprimento", "Polegada (in)", "Centímetro (cm)")
    assert round(res_cm, 4) == 25.4

    # 4. Arroba para Kg
    assert convert_units(2.0, "Massa e Peso", "Arroba (Brasil)", "Quilograma (kg)") == 30.0
    # 5. Grama para Quilo
    assert convert_units(500.0, "Massa e Peso", "Grama (g)", "Quilograma (kg)") == 0.5


def test_unit_converter_digital_data():
    """Valida conversão precisa de unidades de dados binárias e decimais."""
    # 8 bits = 1 Byte
    assert convert_units(8.0, "Dados Digitais", "Bit (b)", "Byte (B)") == 1.0
    # 1 GiB = 1024 MiB
    assert convert_units(1.0, "Dados Digitais", "Gibibyte (GiB - 1024 MiB)", "Mebibyte (MiB - 1024 KiB)") == 1024.0
    # 1024 KiB = 1048576 Bytes
    assert convert_units(1024.0, "Dados Digitais", "Kibibyte (KiB - 1024 B)", "Byte (B)") == 1048576.0


def test_unit_converter_temperature_edge_cases():
    """Valida conversões termométricas e pontos notáveis."""
    # Ponto de congelamento da água
    assert convert_temperature(0.0, "Celsius (°C)", "Fahrenheit (°F)") == 32.0
    assert convert_temperature(0.0, "Celsius (°C)", "Kelvin (K)") == 273.15

    # Ponto de ebulição da água
    assert convert_temperature(100.0, "Celsius (°C)", "Fahrenheit (°F)") == 212.0
    assert convert_temperature(100.0, "Celsius (°C)", "Kelvin (K)") == 373.15

    # Ponto de convergência Celsius e Fahrenheit (-40°)
    assert convert_temperature(-40.0, "Celsius (°C)", "Fahrenheit (°F)") == -40.0
    assert convert_temperature(-40.0, "Fahrenheit (°F)", "Celsius (°C)") == -40.0

    # Retorno idêntico
    assert convert_temperature(25.0, "Celsius (°C)", "Celsius (°C)") == 25.0

    # Exceção para categoria ou unidade inválida
    with pytest.raises(ValueError):
        convert_units(10.0, "Comprimento", "Metro (m)", "UnidadeInvalida")


def test_unit_converter_view(qapp):
    """Valida interação com a interface gráfica do conversor."""
    tool = UnitConverterTool()
    view = UnitConverterView(tool)

    # Selecionar categoria "Comprimento"
    idx = view.combo_category.findText("Comprimento")
    assert idx >= 0
    view.combo_category.setCurrentIndex(idx)

    # Definir 1000 metros para quilômetros
    idx_from = view.combo_from.findText("Metro (m)")
    idx_to = view.combo_to.findText("Quilômetro (km)")
    assert idx_from >= 0
    assert idx_to >= 0
    view.combo_from.setCurrentIndex(idx_from)
    view.combo_to.setCurrentIndex(idx_to)

    view.spin_value.setValue(2500.0)
    view._calculate()

    # O resultado deve ser "2.5"
    assert "2.5" in view.edit_result.text()

    # Inverter unidades
    view._swap_units()
    assert view.combo_from.currentText() == "Quilômetro (km)"
    assert view.combo_to.currentText() == "Metro (m)"
