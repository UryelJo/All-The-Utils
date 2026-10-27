"""
Lógica pura para conversão e transformação de casos tipográficos e estilos de identificadores.

Formatos suportados:
- camelCase
- PascalCase
- snake_case
- CONSTANT_CASE (SCREAMING_SNAKE_CASE)
- kebab-case
- Title Case
- Sentence case
- Train-Case (Header-Case)
- dot.case
- path/case
- aLtErNaTiNg cAsE
- iNVERSE cASE
- Limpeza de diacríticos/acentos Unicode (opcional)

Isolado de qualquer biblioteca de interface gráfica.
"""
import re
import unicodedata
from typing import Dict, List, Optional


def remove_accents(text: str) -> str:
    """
    Remove acentos e diacríticos de uma string, normalizando para ASCII aproximado.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _split_into_words(text: str) -> List[str]:
    """
    Divide um identificador ou frase em uma lista de palavras atômicas,
    lidando com camelCase, snake_case, hífens, pontuações e espaços.
    """
    if not text:
        return []

    # Divide onde há transição de minúscula para maiúscula (ex: camelCase -> camel Case)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    # Divide onde há sequências de maiúsculas seguidas de minúsculas (ex: XMLParser -> XML Parser)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    # Substitui caracteres não alfanuméricos por espaço
    s = re.sub(r"[^a-zA-Z0-9\u00C0-\u017F]+", " ", s)
    
    words = [w for w in s.strip().split() if w]
    return words


def to_camel_case(text: str, strip_accents: bool = False) -> str:
    """Converte para camelCase (ex: primeiroExemploDeTexto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    if not words:
        return ""
    first = words[0].lower()
    rest = [w.capitalize() for w in words[1:]]
    return first + "".join(rest)


def to_pascal_case(text: str, strip_accents: bool = False) -> str:
    """Converte para PascalCase (ex: PrimeiroExemploDeTexto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return "".join(w.capitalize() for w in words)


def to_snake_case(text: str, strip_accents: bool = False) -> str:
    """Converte para snake_case (ex: primeiro_exemplo_de_texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return "_".join(w.lower() for w in words)


def to_constant_case(text: str, strip_accents: bool = False) -> str:
    """Converte para CONSTANT_CASE / SCREAMING_SNAKE_CASE (ex: PRIMEIRO_EXEMPLO_DE_TEXTO)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return "_".join(w.upper() for w in words)


def to_kebab_case(text: str, strip_accents: bool = False) -> str:
    """Converte para kebab-case (ex: primeiro-exemplo-de-texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return "-".join(w.lower() for w in words)


def to_title_case(text: str, strip_accents: bool = False) -> str:
    """Converte para Title Case (ex: Primeiro Exemplo De Texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return " ".join(w.capitalize() for w in words)


def to_sentence_case(text: str, strip_accents: bool = False) -> str:
    """Converte para Sentence case (ex: Primeiro exemplo de texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    if not words:
        return ""
    first = words[0].capitalize()
    rest = [w.lower() for w in words[1:]]
    return " ".join([first] + rest)


def to_train_case(text: str, strip_accents: bool = False) -> str:
    """Converte para Train-Case / Header-Case (ex: Primeiro-Exemplo-De-Texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return "-".join(w.capitalize() for w in words)


def to_dot_case(text: str, strip_accents: bool = False) -> str:
    """Converte para dot.case (ex: primeiro.exemplo.de.texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return ".".join(w.lower() for w in words)


def to_path_case(text: str, strip_accents: bool = False) -> str:
    """Converte para path/case (ex: primeiro/exemplo/de/texto)."""
    if strip_accents:
        text = remove_accents(text)
    words = _split_into_words(text)
    return "/".join(w.lower() for w in words)


def to_alternating_case(text: str, strip_accents: bool = False) -> str:
    """Alterna maiúsculas e minúsculas caractere por caractere (ex: pRiMeIrO eXeMpLo)."""
    if strip_accents:
        text = remove_accents(text)
    res = []
    upper = False
    for char in text:
        if char.isalpha():
            res.append(char.upper() if upper else char.lower())
            upper = not upper
        else:
            res.append(char)
    return "".join(res)


def to_inverse_case(text: str, strip_accents: bool = False) -> str:
    """Inverte maiúsculas e minúsculas mantendo pontuação intacta."""
    if strip_accents:
        text = remove_accents(text)
    return text.swapcase()


CONVERTERS = {
    "camelCase": to_camel_case,
    "PascalCase": to_pascal_case,
    "snake_case": to_snake_case,
    "CONSTANT_CASE": to_constant_case,
    "kebab-case": to_kebab_case,
    "Title Case": to_title_case,
    "Sentence case": to_sentence_case,
    "Train-Case": to_train_case,
    "dot.case": to_dot_case,
    "path/case": to_path_case,
    "Alternating Case": to_alternating_case,
    "Invert Case": to_inverse_case,
}


def convert_all_cases(text: str, strip_accents: bool = False) -> Dict[str, str]:
    """
    Gera um dicionário com todas as variantes de caixa para o texto fornecido.
    """
    return {
        key: func(text, strip_accents=strip_accents)
        for key, func in CONVERTERS.items()
    }


def convert_multiline(text: str, case_format: str, strip_accents: bool = False) -> str:
    """
    Converte um texto preservando quebras de linha linha por linha.
    """
    func = CONVERTERS.get(case_format)
    if not func:
        return text
    lines = text.split("\n")
    converted_lines = [func(line, strip_accents=strip_accents) for line in lines]
    return "\n".join(converted_lines)
