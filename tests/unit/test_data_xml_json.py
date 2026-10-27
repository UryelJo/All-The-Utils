"""
Testes unitários rigorosos para o conversor bidirecional XML e JSON (data.xml_json).
Validações semânticas, atributos @, preservação de hierarquias e robustez a erros.
"""
import json
import xml.etree.ElementTree as ET
import pytest

from wintoolbox.tools.data.xml_json.logic import (
    dict_to_xml,
    json_to_xml,
    xml_to_dict,
    xml_to_json,
)
from wintoolbox.tools.data.xml_json.tool import XmlJsonTool


def test_xml_to_json_attributes_and_lists():
    xml_input = (
        '<biblioteca local="Brasil">\n'
        '  <livro id="1" idioma="pt">\n'
        '    <titulo>Dom Casmurro</titulo>\n'
        '    <autor>Machado de Assis</autor>\n'
        '  </livro>\n'
        '  <livro id="2" idioma="en">\n'
        '    <titulo>1984</titulo>\n'
        '    <autor>George Orwell</autor>\n'
        '  </livro>\n'
        '</biblioteca>'
    )

    data = xml_to_dict(xml_input)
    assert "biblioteca" in data
    assert data["biblioteca"]["@local"] == "Brasil"

    livros = data["biblioteca"]["livro"]
    assert isinstance(livros, list)
    assert len(livros) == 2

    assert livros[0]["@id"] == "1"
    assert livros[0]["@idioma"] == "pt"
    assert livros[0]["titulo"] == "Dom Casmurro"
    assert livros[0]["autor"] == "Machado de Assis"

    assert livros[1]["@id"] == "2"
    assert livros[1]["titulo"] == "1984"


def test_json_to_xml_and_semantic_validation():
    json_input = json.dumps({
        "empresa": {
            "@cnpj": "12345678000199",
            "departamento": {
                "@nome": "TI",
                "colaborador": ["Carlos", "Mariana"],
            },
        }
    })

    xml_output = json_to_xml(json_input, include_declaration=True)
    assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_output
    assert '<empresa cnpj="12345678000199">' in xml_output
    assert '<departamento nome="TI">' in xml_output
    assert '<colaborador>Carlos</colaborador>' in xml_output
    assert '<colaborador>Mariana</colaborador>' in xml_output

    # Validação do Efeito Real: deve ser um XML válido interpretável por ElementTree
    root = ET.fromstring(xml_output.split("\n", 1)[1])
    assert root.tag == "empresa"
    assert root.attrib["cnpj"] == "12345678000199"


def test_xml_json_errors_and_edge_cases():
    with pytest.raises(ValueError, match="vazio"):
        xml_to_dict("")

    with pytest.raises(ValueError, match="sintaxe no XML"):
        xml_to_dict("<aberto><nao_fechado>")

    with pytest.raises(ValueError, match="vazio"):
        json_to_xml("   ")

    with pytest.raises(ValueError, match="sintaxe no JSON"):
        json_to_xml("{json_invalido: 123")


def test_xml_json_tool_ui(qtbot):
    tool = XmlJsonTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Carrega exemplo de demonstração
    view._load_sample()
    assert "catalogo" in view._txt_json.toPlainText()
    assert "cluster-prod-01" in view._txt_json.toPlainText()
    assert "sucesso" in view._lbl_status.text()

    # Testa conversão inversa JSON -> XML
    view._convert_json_to_xml()
    assert '<catalogo versao="2.0">' in view._txt_xml.toPlainText()
    assert "cluster-prod-01" in view._txt_xml.toPlainText()
