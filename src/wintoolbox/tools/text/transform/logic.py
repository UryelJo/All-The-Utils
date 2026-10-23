"""
Lógica pura da ferramenta Transformações de Texto e Manipulação de Linhas.
Isolada de componentes visuais do Qt.
"""
from dataclasses import dataclass
import re
from typing import Dict, List
import unicodedata


@dataclass
class TextStats:
    characters: int
    words: int
    lines: int
    bytes_utf8: int


def remove_accents(text: str) -> str:
    """Remove acentos e diacríticos mantendo letras base."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def to_camel_case(text: str) -> str:
    """Converte texto para camelCase."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    words = re.findall(r"[A-Za-z0-9]+", s)
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def to_snake_case(text: str) -> str:
    """Converte texto para snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    words = re.findall(r"[A-Za-z0-9]+", s)
    return "_".join(w.lower() for w in words)


def to_kebab_case(text: str) -> str:
    """Converte texto para kebab-case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    words = re.findall(r"[A-Za-z0-9]+", s)
    return "-".join(w.lower() for w in words)


def to_slug(text: str) -> str:
    """Gera um slug web amigável (sem acentos e com hífens)."""
    clean = remove_accents(text.lower())
    clean = re.sub(r"[^a-z0-9]+", "-", clean)
    return clean.strip("-")


def sort_lines(text: str, reverse: bool = False) -> str:
    """Ordena as linhas de um texto de forma crescente ou decrescente."""
    lines = text.splitlines()
    return "\n".join(sorted(lines, reverse=reverse))


def dedup_lines(text: str) -> str:
    """Remove linhas duplicadas preservando a ordem da primeira aparição."""
    lines = text.splitlines()
    seen = set()
    unique: List[str] = []
    for l in lines:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return "\n".join(unique)


def remove_empty_lines(text: str) -> str:
    """Remove linhas em branco ou contendo apenas espaços."""
    lines = text.splitlines()
    return "\n".join([l for l in lines if l.strip()])


def reverse_lines(text: str) -> str:
    """Inverte a ordem das linhas de cima para baixo."""
    lines = text.splitlines()
    return "\n".join(reversed(lines))


def number_lines(text: str) -> str:
    """Adiciona numeração 1., 2., 3. no início de cada linha."""
    lines = text.splitlines()
    return "\n".join([f"{i + 1}. {l}" for i, l in enumerate(lines)])


def trim_lines(text: str) -> str:
    """Remove espaços em branco no início e final de cada linha."""
    lines = text.splitlines()
    return "\n".join([l.strip() for l in lines])


def apply_affixes(text: str, prefix: str = "", suffix: str = "") -> str:
    """Aplica prefixo e/ou sufixo a todas as linhas do texto."""
    lines = text.splitlines()
    return "\n".join([f"{prefix}{l}{suffix}" for l in lines])


def compute_text_stats(text: str) -> TextStats:
    """Calcula estatísticas de caracteres, palavras, linhas e bytes UTF-8."""
    chars = len(text)
    words = len(text.split()) if text.strip() else 0
    lines = len(text.splitlines()) if text else 0
    b_size = len(text.encode("utf-8"))
    return TextStats(
        characters=chars,
        words=words,
        lines=lines,
        bytes_utf8=b_size,
    )
