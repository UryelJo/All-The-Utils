"""
Lógica pura para teste e avaliação de expressões regulares (RegEx).

Suporta análise de grupos de captura nominados e posicionais, substituições,
validação de sintaxe e catálogo de padrões comuns pré-configurados.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("text.regex_tester.logic")

COMMON_REGEX_PATTERNS: Dict[str, Dict[str, str]] = {
    "E-mail": {
        "pattern": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "description": "Endereços de e-mail padrão RFC 5322 simplificado"
    },
    "CPF (Brasil)": {
        "pattern": r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        "description": "Cadastro de Pessoas Físicas com ou sem pontuação"
    },
    "CNPJ (Brasil)": {
        "pattern": r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        "description": "Cadastro Nacional da Pessoa Jurídica"
    },
    "CEP (Brasil)": {
        "pattern": r"\b\d{5}-?\d{3}\b",
        "description": "Código de Endereçamento Postal brasileiro"
    },
    "Telefone Celular (BR)": {
        "pattern": r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?9\s?\d{4}[-.\s]?\d{4}",
        "description": "Telefones celulares com DDD e nono dígito"
    },
    "Data (DD/MM/AAAA)": {
        "pattern": r"\b(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/\d{4}\b",
        "description": "Datas no formato dia/mês/ano de 4 dígitos"
    },
    "URL (HTTP / HTTPS)": {
        "pattern": r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*",
        "description": "Links de internet e páginas web"
    },
    "Endereço IPv4": {
        "pattern": r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "description": "Endereços IP em formato decimal pontuado"
    },
    "Cor Hexadecimal": {
        "pattern": r"#(?:[0-9a-fA-F]{3}){1,2}\b",
        "description": "Cores hex (#RGB ou #RRGGBB)"
    },
}


@dataclass
class RegexMatchItem:
    index: int
    span: Tuple[int, int]
    full_match: str
    groups: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def find_regex_matches(pattern_str: str, text: str, flags: int = 0) -> List[RegexMatchItem]:
    """
    Localiza todas as ocorrências de um padrão regex no texto.

    Raises:
        re.error: Se a sintaxe da expressão regular for inválida.
    """
    if not pattern_str:
        return []

    compiled = re.compile(pattern_str, flags)
    matches: List[RegexMatchItem] = []

    for idx, match in enumerate(compiled.finditer(text), 1):
        groups_dict: Dict[str, str] = {}
        for g_idx, g_val in enumerate(match.groups(), 1):
            groups_dict[f"Grupo {g_idx}"] = g_val if g_val is not None else ""

        # Grupos nomeados
        for k, v in match.groupdict().items():
            groups_dict[f"Nome '{k}'"] = v if v is not None else ""

        matches.append(RegexMatchItem(
            index=idx,
            span=match.span(),
            full_match=match.group(0),
            groups=groups_dict
        ))

    return matches


def apply_regex_replace(pattern_str: str, replacement_str: str, text: str, flags: int = 0) -> str:
    """
    Aplica substituição regex em um texto.
    """
    if not pattern_str:
        return text

    compiled = re.compile(pattern_str, flags)
    return compiled.sub(replacement_str, text)
