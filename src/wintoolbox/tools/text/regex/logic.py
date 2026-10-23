"""
Lógica pura da ferramenta Testador de Expressões Regulares (Regex).
Isolada de componentes visuais do Qt.
"""
from dataclasses import dataclass
import re
from typing import List, Optional, Tuple


@dataclass
class RegexMatchItem:
    index: int
    text: str
    start: int
    end: int
    groups: Tuple[str, ...]


@dataclass
class RegexEvaluationResult:
    is_valid: bool
    error_message: Optional[str]
    matches: List[RegexMatchItem]
    substituted_text: str


def evaluate_regex(
    pattern: str,
    text: str,
    replacement: str = "",
    ignore_case: bool = False,
    multiline: bool = False,
    dotall: bool = False,
) -> RegexEvaluationResult:
    """
    Executa compilação e matching de uma expressão regular sobre um texto de entrada.
    Também gera a string resultante da substituição.
    """
    if not pattern:
        return RegexEvaluationResult(
            is_valid=True,
            error_message="Informe um padrão regex.",
            matches=[],
            substituted_text=text,
        )

    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE
    if multiline:
        flags |= re.MULTILINE
    if dotall:
        flags |= re.DOTALL

    try:
        compiled = re.compile(pattern, flags)
        raw_matches = list(compiled.finditer(text))
        
        matches: List[RegexMatchItem] = []
        for i, m in enumerate(raw_matches):
            matches.append(
                RegexMatchItem(
                    index=i + 1,
                    text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    groups=tuple(g if g is not None else "" for g in m.groups()),
                )
            )

        sub_res = compiled.sub(replacement, text)
        return RegexEvaluationResult(
            is_valid=True,
            error_message=None,
            matches=matches,
            substituted_text=sub_res,
        )
    except re.error as e:
        return RegexEvaluationResult(
            is_valid=False,
            error_message=f"Erro de sintaxe no Regex: {str(e)}",
            matches=[],
            substituted_text=text,
        )
