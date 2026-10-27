"""
Testes unitários rigorosos para operações de conjuntos entre listas de texto.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
import pytest
from wintoolbox.tools.text.list_ops.logic import (
    execute_list_operation,
    ListOperation,
    natural_sort_key,
    parse_lines,
)


def test_parse_lines():
    """Valida separação de linhas com e sem trim/linhas vazias."""
    raw = "  item1  \n\n\titem2\n   \nitem3"
    lines = parse_lines(raw, strip_whitespace=True, ignore_empty=True)
    assert lines == ["item1", "item2", "item3"]

    lines_raw = parse_lines(raw, strip_whitespace=False, ignore_empty=False)
    assert len(lines_raw) == 5


def test_set_operations_deterministic():
    """Valida união, interseção e diferenças entre duas listas."""
    list_a = ["maçã", "banana", "laranja", "uva"]
    list_b = ["laranja", "uva", "abacaxi", "melancia"]

    # Interseção: itens presentes em ambas
    intersect = execute_list_operation(list_a, list_b, ListOperation.INTERSECTION)
    assert intersect == ["laranja", "uva"]

    # Diferença A - B: presentes apenas em A
    diff_a = execute_list_operation(list_a, list_b, ListOperation.DIFF_A_MINUS_B)
    assert diff_a == ["maçã", "banana"]

    # Diferença B - A: presentes apenas em B
    diff_b = execute_list_operation(list_a, list_b, ListOperation.DIFF_B_MINUS_A)
    assert diff_b == ["abacaxi", "melancia"]

    # Diferença Simétrica: presentes em A ou em B, mas não em ambos
    sym_diff = execute_list_operation(list_a, list_b, ListOperation.SYMMETRIC_DIFF)
    assert sym_diff == ["maçã", "banana", "abacaxi", "melancia"]

    # União sem duplicatas preservando ordem
    union = execute_list_operation(list_a, list_b, ListOperation.UNION)
    assert union == ["maçã", "banana", "laranja", "uva", "abacaxi", "melancia"]


def test_case_insensitivity_and_sorting():
    """Valida comparação case-insensitive e ordenação natural."""
    list_a = ["Item2", "item10", "ITEM1"]
    list_b = ["item1", "ITEM2"]

    # Interseção case-insensitive: "Item2" e "ITEM1" coincidem
    intersect = execute_list_operation(
        list_a,
        list_b,
        ListOperation.INTERSECTION,
        case_sensitive=False,
        sort_order="natural",
    )
    # Na ordenação natural: item 1 vem antes de item 2
    assert intersect == ["ITEM1", "Item2"]

    # Ordenação natural em lista com dezenas
    sample = ["file10.txt", "file2.txt", "file1.txt"]
    sample.sort(key=natural_sort_key)
    assert sample == ["file1.txt", "file2.txt", "file10.txt"]
