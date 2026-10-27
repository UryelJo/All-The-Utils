"""
Testes unitários rigorosos para o Conversor de Caixa Tipográfica (text.case_converter).
Validações exatas, zero asserções frouxas, casos de borda e tratamento de acentuação.
"""
import pytest
from PySide6.QtWidgets import QApplication

from wintoolbox.tools.text.case_converter.logic import (
    CONVERTERS,
    convert_all_cases,
    convert_multiline,
    remove_accents,
    to_alternating_case,
    to_camel_case,
    to_constant_case,
    to_dot_case,
    to_inverse_case,
    to_kebab_case,
    to_pascal_case,
    to_path_case,
    to_sentence_case,
    to_snake_case,
    to_title_case,
    to_train_case,
)
from wintoolbox.tools.text.case_converter.tool import CaseConverterTool


def test_remove_accents_exact():
    raw = "Atenção! João foi à farmácia e comprou açúcar & maçã."
    expected = "Atencao! Joao foi a farmacia e comprou acucar & maca."
    assert remove_accents(raw) == expected
    assert remove_accents("") == ""


def test_converters_standard_phrase():
    input_text = "WinToolbox utilitários para Windows"

    # camelCase
    assert to_camel_case(input_text, strip_accents=True) == "winToolboxUtilitariosParaWindows"
    # PascalCase
    assert to_pascal_case(input_text, strip_accents=True) == "WinToolboxUtilitariosParaWindows"
    # snake_case
    assert to_snake_case(input_text, strip_accents=True) == "win_toolbox_utilitarios_para_windows"
    # CONSTANT_CASE
    assert to_constant_case(input_text, strip_accents=True) == "WIN_TOOLBOX_UTILITARIOS_PARA_WINDOWS"
    # kebab-case
    assert to_kebab_case(input_text, strip_accents=True) == "win-toolbox-utilitarios-para-windows"
    # Title Case
    assert to_title_case(input_text, strip_accents=True) == "Win Toolbox Utilitarios Para Windows"
    # Sentence case
    assert to_sentence_case(input_text, strip_accents=True) == "Win toolbox utilitarios para windows"
    # Train-Case
    assert to_train_case(input_text, strip_accents=True) == "Win-Toolbox-Utilitarios-Para-Windows"
    # dot.case
    assert to_dot_case(input_text, strip_accents=True) == "win.toolbox.utilitarios.para.windows"
    # path/case
    assert to_path_case(input_text, strip_accents=True) == "win/toolbox/utilitarios/para/windows"


def test_converters_edge_cases():
    # Vazio
    for name, func in CONVERTERS.items():
        res = func("", strip_accents=False)
        assert res == "", f"Falha para formato {name} com string vazia"

    # String com múltiplos espaços e símbolos
    messy = "   ___teste---com___VÁRIOS---delimitadores...   "
    assert to_snake_case(messy, strip_accents=True) == "teste_com_varios_delimitadores"
    assert to_kebab_case(messy, strip_accents=True) == "teste-com-varios-delimitadores"
    assert to_camel_case(messy, strip_accents=True) == "testeComVariosDelimitadores"

    # Invert e Alternating Case
    assert to_inverse_case("PyThOn 3.12!") == "pYtHoN 3.12!"
    alt = to_alternating_case("hello world")
    assert alt == "hElLo WoRlD"


def test_convert_multiline_and_all_cases():
    multiline = "linha um\nlinha dois\nlinha tres"
    converted = convert_multiline(multiline, "snake_case")
    assert converted == "linha_um\nlinha_dois\nlinha_tres"

    all_cases = convert_all_cases("Meu Teste")
    assert "camelCase" in all_cases
    assert all_cases["camelCase"] == "meuTeste"
    assert all_cases["CONSTANT_CASE"] == "MEU_TESTE"


def test_case_converter_tool_ui(qtbot):
    tool = CaseConverterTool()
    widget = tool.create_widget()
    qtbot.addWidget(widget)

    # Simula digitação
    tool._txt_input.setPlainText("gerador de codigo")
    # Verifica se os campos foram atualizados
    assert tool._case_fields["snake_case"].text() == "gerador_de_codigo"
    assert tool._case_fields["camelCase"].text() == "geradorDeCodigo"
    assert tool._case_fields["PascalCase"].text() == "GeradorDeCodigo"

    # Testa ativação de remover acentos
    tool._txt_input.setPlainText("função rápida")
    tool._chk_remove_accents.setChecked(True)
    assert tool._case_fields["snake_case"].text() == "funcao_rapida"

    # Testa cópia
    tool._copy_text(tool._case_fields["snake_case"].text(), "snake_case")
    clipboard = QApplication.clipboard()
    assert clipboard.text() == "funcao_rapida"
