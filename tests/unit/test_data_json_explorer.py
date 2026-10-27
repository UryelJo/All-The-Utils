"""
Testes unitários rigorosos para data.json_explorer.logic.
Segue as Diretrizes de Qualidade Anti-Gambiarra: asserções determinísticas,
Happy Path, Edge Cases e cenários de erro.
"""
import pytest
from wintoolbox.tools.data.json_explorer.logic import (
    calculate_statistics,
    get_value_type_label,
    parse_json,
    query_by_jsonpath,
    search_nodes,
)


def test_parse_json_valid_and_invalid():
    # Happy Path
    raw = '{"nome": "WinToolbox", "versao": 2, "ativo": true, "tags": ["windows", "util"]}'
    ok, data, err = parse_json(raw)
    assert ok is True
    assert err == ""
    assert data["nome"] == "WinToolbox"
    assert data["versao"] == 2
    assert data["ativo"] is True
    assert data["tags"] == ["windows", "util"]

    # Bytes
    ok_b, data_b, err_b = parse_json(raw.encode("utf-8"))
    assert ok_b is True
    assert data_b["nome"] == "WinToolbox"

    # Edge cases: vazio / espaços
    ok_empty, _, err_empty = parse_json("   ")
    assert ok_empty is False
    assert err_empty == "Entrada JSON vazia."

    # Erro de sintaxe
    ok_err, _, err_syntax = parse_json('{"chave": "incompleta"')
    assert ok_err is False
    assert "Erro de sintaxe JSON" in err_syntax


def test_calculate_statistics_and_type_labels():
    data = {
        "sistema": "Windows",
        "codigo": 123,
        "pi": 3.14,
        "disponivel": False,
        "nulo": None,
        "itens": [10, "texto", None],
        "metadados": {
            "autor": "Admin"
        }
    }
    stats = calculate_statistics(data)
    # Total de nós: raiz (dict) + 7 itens do dict raiz + 3 itens do array 'itens' + 1 item do dict 'metadados' = 1 + 7 + 3 + 1 = 12
    assert stats["total_nodes"] == 12
    assert stats["total_keys"] == 8  # 7 no raiz + 1 em metadados
    assert stats["max_depth"] == 3
    assert stats["type_counts"]["string"] == 3  # "Windows", "texto", "Admin"
    assert stats["type_counts"]["number"] == 3  # 123, 3.14, 10
    assert stats["type_counts"]["boolean"] == 1  # False
    assert stats["type_counts"]["null"] == 2  # data["nulo"], itens[2]
    assert stats["type_counts"]["object"] == 2  # raiz, metadados
    assert stats["type_counts"]["array"] == 1  # itens

    assert get_value_type_label(None) == "null"
    assert get_value_type_label(True) == "boolean"
    assert get_value_type_label(42) == "integer"
    assert get_value_type_label(3.14) == "number"
    assert get_value_type_label("ola") == "string"
    assert get_value_type_label([1, 2]) == "array[2]"
    assert get_value_type_label({"a": 1}) == "object{1}"


def test_search_nodes():
    data = {
        "usuario": {
            "nome": "João da Silva",
            "email": "joao@empresa.com.br",
            "perfil": "ADMIN",
            "permissoes": ["ler", "escrever", "deletar_usuario"],
        },
        "config": {
            "timeout_segundos": 30,
            "servidor": "admin.empresa.com.br",
        }
    }
    # Busca por valor
    res_val = search_nodes(data, "joao")
    assert len(res_val) == 2  # Nome e Email
    assert res_val[0]["matched_on"] == "value"
    assert res_val[0]["path"] == "$.usuario.nome"

    # Busca por chave
    res_key = search_nodes(data, "timeout")
    assert len(res_key) == 1
    assert res_key[0]["matched_on"] == "key"
    assert res_key[0]["path"] == "$.config.timeout_segundos"

    # Busca sem resultados
    res_none = search_nodes(data, "termo_inexistente_xyz")
    assert res_none == []


def test_query_by_jsonpath():
    data = {
        "livros": [
            {"id": 1, "titulo": "Python Fluente", "preco": 100},
            {"id": 2, "titulo": "Domain Driven Design", "preco": 120},
            {"id": 3, "titulo": "Código Limpo", "preco": 85},
        ]
    }
    res = query_by_jsonpath(data, "$.livros[*].titulo")
    assert len(res) == 3
    titles = [r["value"] for r in res]
    assert titles == ["Python Fluente", "Domain Driven Design", "Código Limpo"]

    res_filter = query_by_jsonpath(data, "$.livros[?(@.preco < 100)].titulo")
    assert len(res_filter) == 1
    assert res_filter[0]["value"] == "Código Limpo"
