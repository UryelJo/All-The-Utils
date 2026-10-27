"""
Testes unitários rigorosos para data.struct_diff.logic.
Garante comparação semântica estrita, tolerância à formatação e detecção exata de alterações.
"""
import pytest
from wintoolbox.tools.data.struct_diff.logic import (
    diff_structures,
    parse_structured_data,
    summarize_diffs,
)


def test_parse_structured_data_formats():
    # JSON
    ok_json, data_json, fmt_j = parse_structured_data('{"chave": "valor", "num": 42}', "json")
    assert ok_json is True
    assert fmt_j == "json"
    assert data_json == {"chave": "valor", "num": 42}

    # TOML
    toml_str = '[database]\nhost = "localhost"\nport = 5432\n'
    ok_toml, data_toml, fmt_t = parse_structured_data(toml_str, "toml")
    assert ok_toml is True
    assert fmt_t == "toml"
    assert data_toml == {"database": {"host": "localhost", "port": 5432}}

    # Entrada vazia
    ok_empty, _, err_empty = parse_structured_data("   ")
    assert ok_empty is False
    assert err_empty == "Entrada vazia."


def test_diff_structures_identical_with_different_formatting():
    # Chaves em ordens diferentes e espaçamentos distintos devem ser consideradas idênticas
    doc_a = {"b": 2, "a": 1, "lista": [10, 20]}
    doc_b = {"a": 1, "lista": [10, 20], "b": 2}

    diffs = diff_structures(doc_a, doc_b)
    summary = summarize_diffs(diffs)

    assert summary["is_identical"] is True
    assert summary["total_diffs"] == 0
    assert diffs == []


def test_diff_structures_detects_add_remove_modify():
    doc_a = {
        "usuario": "admin",
        "ativo": True,
        "limites": {
            "reqs": 100,
            "removido": "valor_antigo",
        },
        "tags": ["prod", "v1"],
    }
    doc_b = {
        "usuario": "admin",
        "ativo": False,  # modificado
        "limites": {
            "reqs": 100,
            "adicionado": "valor_novo",  # adicionado
        },
        "tags": ["prod", "v1", "v2"],  # lista adicionada
        "novo_campo": 123,  # adicionado
    }

    diffs = diff_structures(doc_a, doc_b)
    summary = summarize_diffs(diffs)

    assert summary["is_identical"] is False
    assert summary["total_diffs"] == 5
    assert summary["modified"] == 1
    assert summary["added"] == 3
    assert summary["removed"] == 1

    diff_map = {d["path"]: d for d in diffs}

    assert diff_map["$.ativo"]["type"] == "modified"
    assert diff_map["$.ativo"]["old_val"] is True
    assert diff_map["$.ativo"]["new_val"] is False

    assert diff_map["$.limites.removido"]["type"] == "removed"
    assert diff_map["$.limites.adicionado"]["type"] == "added"
    assert diff_map["$.novo_campo"]["type"] == "added"
    assert diff_map["$.tags[2]"]["type"] == "added"


def test_diff_structures_type_change():
    doc_a = {"campo": 123}
    doc_b = {"campo": [1, 2, 3]}

    diffs = diff_structures(doc_a, doc_b)
    assert len(diffs) == 1
    assert diffs[0]["type"] == "modified"
    assert diffs[0]["path"] == "$.campo"
    assert "Tipo alterado de int para list" in diffs[0]["detail"]
