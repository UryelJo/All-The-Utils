"""
Testes unitários rigorosos para o avaliador e extrator JSONPath (data.json_path).
Validação determinística de consultas RFC 9535, curingas, recursão e filtros.
"""
import pytest

from wintoolbox.tools.data.json_path.logic import (
    SAMPLE_JSON,
    query_jsonpath,
)
from wintoolbox.tools.data.json_path.tool import JsonPathTool


def test_jsonpath_simple_and_wildcards():
    # Consulta direta
    res_name = query_jsonpath(SAMPLE_JSON, "$.store.name")
    assert len(res_name) == 1
    assert res_name[0].value == "Livraria WinToolbox"

    # Curinga em lista de livros
    res_titles = query_jsonpath(SAMPLE_JSON, "$.store.book[*].title")
    assert len(res_titles) == 4
    extracted_titles = [m.value for m in res_titles]
    assert "O Senhor dos Anéis" in extracted_titles
    assert "Python Avançado e Arquitetura" in extracted_titles
    assert "Fundação" in extracted_titles


def test_jsonpath_recursive_descent():
    # Coleta de todos os campos 'price' na árvore inteira
    res_prices = query_jsonpath(SAMPLE_JSON, "$..price")
    # 4 livros + 1 bicicleta = 5 preços
    assert len(res_prices) == 5
    prices = [m.value for m in res_prices]
    assert 89.90 in prices
    assert 54.00 in prices
    assert 350.00 in prices


def test_jsonpath_filters_and_predicates():
    # Livros com preço menor que 60
    cheap_books = query_jsonpath(SAMPLE_JSON, "$.store.book[?(@.price < 60)]")
    assert len(cheap_books) == 2
    titles = [m.value["title"] for m in cheap_books]
    assert "Python Avançado e Arquitetura" in titles
    assert "Fundação" in titles

    # Livros em estoque (in_stock == True)
    in_stock = query_jsonpath(SAMPLE_JSON, "$.store.book[?(@.in_stock == true)]")
    assert len(in_stock) == 3
    for b in in_stock:
        assert b.value["in_stock"] is True


def test_jsonpath_slices_and_indexes():
    # Primeiro livro [0]
    first = query_jsonpath(SAMPLE_JSON, "$.store.book[0].title")
    assert len(first) == 1
    assert first[0].value == "O Senhor dos Anéis"

    # Último livro [-1]
    last = query_jsonpath(SAMPLE_JSON, "$.store.book[-1].title")
    assert len(last) == 1
    assert last[0].value == "Fundação"

    # Slice [0:2]
    slice_res = query_jsonpath(SAMPLE_JSON, "$.store.book[0:2]")
    assert len(slice_res) == 2


def test_jsonpath_edge_cases():
    assert query_jsonpath(SAMPLE_JSON, "") == []
    assert query_jsonpath(SAMPLE_JSON, "$.inexistente") == []
    assert query_jsonpath({}, "$.qualquer") == []


def test_jsonpath_tool_ui(qtbot):
    tool = JsonPathTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Por padrão ele carrega o sample e executa a query $.store.book[*].title
    assert view._table_view.visible_count() == 4
    assert "O Senhor dos Anéis" in view._txt_raw_out.toPlainText()

    # Testa mudança de expressão para $..price
    view._txt_expr.setText("$..price")
    view._run_query()
    assert view._table_view.visible_count() == 5
    assert "5 nó(s) encontrado(s)" in view._lbl_status.text()
