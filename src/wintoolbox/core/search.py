"""
Módulo de busca e ranqueamento com prioridade rigorosa:
1º Prioridade: Nome da Ferramenta
2º Prioridade: Descrição da Ferramenta
3º Prioridade: Palavras-chave, Categoria, ID e Extensões
"""
import re
import unicodedata
from typing import List, Optional, Tuple
from rapidfuzz import fuzz

from wintoolbox.core.registry import BaseTool


def normalize_search_text(text: str) -> str:
    """Remove acentos, pontuação excessiva e converte para minúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    return cleaned


def calculate_tool_relevance(tool: BaseTool, query: str) -> int:
    """
    Calcula a relevância de uma ferramenta com base na consulta:
    Retorna 0 se a ferramenta não corresponder aos critérios.
    Valores maiores significam maior relevância.

    Hierarquia:
      >= 500: Correspondência no Nome (Prioridade 1)
      100 - 300: Correspondência na Descrição (Prioridade 2)
      10 - 80: Correspondência em Keywords, Categoria, ID ou Extensões (Prioridade 3)
    """
    q = normalize_search_text(query)
    if not q:
        return 1

    name = normalize_search_text(getattr(tool, "name", "") or getattr(tool, "title", "") or tool.id)
    desc = normalize_search_text(getattr(tool, "description", ""))
    cat = normalize_search_text(getattr(tool, "category", ""))
    tid = normalize_search_text(getattr(tool, "id", ""))
    keywords = [normalize_search_text(k) for k in getattr(tool, "keywords", []) or []]
    kw_str = " ".join(keywords)
    exts = [normalize_search_text(e) for e in getattr(tool, "accepts", []) or []]
    ext_str = " ".join(exts)

    score = 0

    # ---------------------------------------------------------
    # PRIORIDADE 1: Nome da Ferramenta
    # ---------------------------------------------------------
    if q == name:
        score += 2000
    elif name.startswith(q):
        score += 1500
    elif q in name:
        # Bônus se for palavra isolada no nome
        if re.search(r"\b" + re.escape(q) + r"\b", name):
            score += 1200
        else:
            score += 1000
    elif len(q) >= 3 and fuzz.partial_ratio(q, name) >= 82:
        score += 550

    # ---------------------------------------------------------
    # PRIORIDADE 2: Descrição da Ferramenta
    # ---------------------------------------------------------
    if q in desc:
        if re.search(r"\b" + re.escape(q) + r"\b", desc):
            score += 250
        else:
            score += 150
    else:
        # Verifica se todas as palavras da query estão presentes na descrição
        words = [w for w in q.split() if len(w) >= 2]
        if len(words) > 1 and all(w in desc for w in words):
            score += 120

    # ---------------------------------------------------------
    # PRIORIDADE 3: Palavras-chave, Categoria, ID e Extensões
    # ---------------------------------------------------------
    if any(q == k for k in keywords):
        score += 80
    elif q in kw_str:
        score += 60

    if q in tid:
        score += 40

    if any(q == e.lstrip(".") for e in exts) or q in ext_str:
        score += 35

    if q in cat:
        score += 20

    return score


def search_and_rank_tools(tools: List[BaseTool], query: str) -> List[Tuple[BaseTool, int]]:
    """
    Filtra e ordena a lista de ferramentas por relevância decrescente:
    Ferramentas com match no Nome sempre aparecem antes das que batem apenas na Descrição.
    """
    if not query.strip():
        return [(t, 1) for t in tools]

    results = []
    for t in tools:
        score = calculate_tool_relevance(t, query)
        if score > 0:
            results.append((t, score))

    # Ordena por score decrescente e, em caso de empate, por nome alfabético
    results.sort(key=lambda item: (-item[1], normalize_search_text(item[0].name)))
    return results
