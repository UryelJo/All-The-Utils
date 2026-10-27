"""
Testes unitários rigorosos do módulo de busca com prioridade Nome > Descrição.
Garante:
1. Relevância maior para correspondência no Nome do que na Descrição.
2. Suporte a termos contidos em descrições detalhadas.
3. Ausência total de ferramentas com name vazio no registro.
4. Nenhuma ferramenta renderizada apenas como '[Lote]' ou vazio.
"""
from typing import List
import pytest

from wintoolbox.core.registry import BaseTool, Tool, FileTool, get_all_tools, get_tool
from wintoolbox.core.search import calculate_tool_relevance, search_and_rank_tools, normalize_search_text


class DummyToolName(Tool):
    id = "dummy.name_match"
    name = "Calculadora Financeira Avançada"
    category = "Calculadoras"
    description = "Ferramenta para cálculos genéricos e relatórios."


class DummyToolDesc(Tool):
    id = "dummy.desc_match"
    name = "Simulador Genérico"
    category = "Calculadoras"
    description = "Realiza cálculos de juros e cálculos de financeira para empréstimos bancários."


def test_search_priority_name_over_description():
    """Valida que uma ferramenta com o termo no Nome tem prioridade estrita sobre quem só tem na Descrição."""
    t_name = DummyToolName()
    t_desc = DummyToolDesc()

    query = "financeira"
    score_name = calculate_tool_relevance(t_name, query)
    score_desc = calculate_tool_relevance(t_desc, query)

    assert score_name > 0
    assert score_desc > 0
    # Prioridade do Nome DEVE ser expressivamente superior à da Descrição
    assert score_name > score_desc, f"Score no nome ({score_name}) deve ser maior que na descrição ({score_desc})"

    # Ao ranquear, t_name deve obrigatoriamente vir antes de t_desc
    ranked = search_and_rank_tools([t_desc, t_name], query)
    assert len(ranked) == 2
    assert ranked[0][0].id == "dummy.name_match"
    assert ranked[1][0].id == "dummy.desc_match"


def test_search_matches_description_terms():
    """Valida que termos presentes apenas nas descrições detalhadas são encontrados com sucesso."""
    t_desc = DummyToolDesc()

    assert calculate_tool_relevance(t_desc, "empréstimos") > 0
    assert calculate_tool_relevance(t_desc, "emprestimos") > 0  # sem acento
    assert calculate_tool_relevance(t_desc, "bancários") > 0
    assert calculate_tool_relevance(t_desc, "juros") > 0


def test_all_registered_tools_have_non_empty_names():
    """Garante que 100% das ferramentas registradas possuam atributo 'name' preenchido e não-vazio."""
    all_tools = get_all_tools()
    assert len(all_tools) >= 261

    for tool in all_tools:
        name = getattr(tool, "name", "").strip()
        assert name != "", f"Ferramenta '{tool.id}' possui atributo 'name' vazio!"
        assert name != "[Lote]", f"Ferramenta '{tool.id}' possui nome '[Lote]' indevido!"
        assert getattr(tool, "description", "").strip() != "", f"Ferramenta '{tool.id}' possui description vazia!"


def test_real_tools_search_priority():
    """Testa a prioridade na base real de ferramentas registradas do WinToolbox."""
    tools = get_all_tools()

    # Busca por 'PDF': Ferramentas com 'PDF' no nome devem pontuar mais alto do que as que só mencionam no texto
    results = search_and_rank_tools(tools, "PDF")
    assert len(results) > 0

    first_tool, first_score = results[0]
    assert "pdf" in normalize_search_text(first_tool.name) or normalize_search_text(first_tool.name).startswith("pdf")
    assert first_score >= 1000

    # Busca por 'Wi-Fi': Ferramenta com 'Wi-Fi' no nome deve vir no topo
    wifi_results = search_and_rank_tools(tools, "Wi-Fi")
    assert len(wifi_results) > 0
    top_wifi, _ = wifi_results[0]
    assert "wifi" in normalize_search_text(top_wifi.name) or "wi-fi" in normalize_search_text(top_wifi.name)
