"""
Lógica pura para operações de conjuntos e manipulação entre duas listas de texto.

Operações suportadas:
- União (A ∪ B)
- Interseção (A ∩ B)
- Diferença A - B (Exclusivos da Lista A)
- Diferença B - A (Exclusivos da Lista B)
- Diferença Simétrica (A Δ B)
- Concatenação (A + B)
- Deduplicação
- Ordenação natural e alfabética (A-Z / Z-A)
- Normalização de maiúsculas/minúsculas e espaços em branco

Isolado de qualquer biblioteca de interface gráfica.
"""
from enum import Enum
import re
from typing import Callable, Iterable, List, Set, Tuple


class ListOperation(str, Enum):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFF_A_MINUS_B = "diff_a_minus_b"
    DIFF_B_MINUS_A = "diff_b_minus_a"
    SYMMETRIC_DIFF = "symmetric_diff"
    CONCAT = "concat"


def natural_sort_key(s: str) -> List[object]:
    """
    Chave para ordenação natural de strings contendo números.
    Exemplo: 'item2' vem antes de 'item10'.
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def parse_lines(
    text: str,
    strip_whitespace: bool = True,
    ignore_empty: bool = True
) -> List[str]:
    """
    Divide um texto em uma lista de linhas individuais, aplicando limpeza se solicitado.
    """
    lines = text.splitlines()
    result = []
    for line in lines:
        cleaned = line.strip() if strip_whitespace else line
        if ignore_empty and not cleaned:
            continue
        result.append(cleaned)
    return result


def execute_list_operation(
    list_a: List[str],
    list_b: List[str],
    operation: ListOperation,
    case_sensitive: bool = True,
    deduplicate: bool = True,
    sort_order: str = "none"  # "none", "asc", "desc", "natural"
) -> List[str]:
    """
    Executa a operação matemática de conjuntos especificada entre as listas A e B.
    """
    def _norm(item: str) -> str:
        return item if case_sensitive else item.lower()

    norm_a = [_norm(x) for x in list_a]
    norm_b = [_norm(x) for x in list_b]

    set_norm_a = set(norm_a)
    set_norm_b = set(norm_b)

    raw_result: List[str] = []

    if operation == ListOperation.UNION:
        # A união preserva a primeira aparição de cada item
        seen_norms = set()
        for orig, norm in zip(list_a, norm_a):
            if norm not in seen_norms:
                seen_norms.add(norm)
                raw_result.append(orig)
        for orig, norm in zip(list_b, norm_b):
            if norm not in seen_norms:
                seen_norms.add(norm)
                raw_result.append(orig)

    elif operation == ListOperation.INTERSECTION:
        # Elementos presentes em ambas as listas
        seen_norms = set()
        for orig, norm in zip(list_a, norm_a):
            if norm in set_norm_b and norm not in seen_norms:
                seen_norms.add(norm)
                raw_result.append(orig)

    elif operation == ListOperation.DIFF_A_MINUS_B:
        # Elementos em A que não existem em B
        seen_norms = set()
        for orig, norm in zip(list_a, norm_a):
            if norm not in set_norm_b:
                if not deduplicate or norm not in seen_norms:
                    seen_norms.add(norm)
                    raw_result.append(orig)

    elif operation == ListOperation.DIFF_B_MINUS_A:
        # Elementos em B que não existem em A
        seen_norms = set()
        for orig, norm in zip(list_b, norm_b):
            if norm not in set_norm_a:
                if not deduplicate or norm not in seen_norms:
                    seen_norms.add(norm)
                    raw_result.append(orig)

    elif operation == ListOperation.SYMMETRIC_DIFF:
        # Elementos em A ou em B, mas não em ambos
        seen_norms = set()
        for orig, norm in zip(list_a, norm_a):
            if norm not in set_norm_b:
                if not deduplicate or norm not in seen_norms:
                    seen_norms.add(norm)
                    raw_result.append(orig)
        for orig, norm in zip(list_b, norm_b):
            if norm not in set_norm_a:
                if not deduplicate or norm not in seen_norms:
                    seen_norms.add(norm)
                    raw_result.append(orig)

    elif operation == ListOperation.CONCAT:
        combined = list_a + list_b
        if deduplicate:
            seen_norms = set()
            for orig in combined:
                norm = _norm(orig)
                if norm not in seen_norms:
                    seen_norms.add(norm)
                    raw_result.append(orig)
        else:
            raw_result = combined

    # Ordenação se solicitada
    if sort_order == "asc":
        raw_result.sort(key=lambda s: s.lower() if not case_sensitive else s)
    elif sort_order == "desc":
        raw_result.sort(key=lambda s: s.lower() if not case_sensitive else s, reverse=True)
    elif sort_order == "natural":
        raw_result.sort(key=natural_sort_key)

    return raw_result
