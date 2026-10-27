"""
Lógica pura para detecção, análise e higienização de caracteres Unicode suspeitos e problemáticos.

Identifica e trata:
- Caracteres de largura zero (Zero-Width Space, ZWNJ, ZWJ, BOM, etc.)
- Espaços atípicos (NBSP, En/Em space, Thin space)
- Homóglifos (caracteres de outros alfabetos como cirílico/grego visualmente idênticos a latinos)
- Aspas tipográficas ("smart quotes") e hífens estilizados
- Normalização canônica Unicode (NFC, NFD, NFKC, NFKD)

Isolado de qualquer biblioteca de interface gráfica.
"""
from dataclasses import dataclass
import unicodedata
from typing import Dict, List, Optional, Tuple


# Caracteres de largura zero (Zero-Width) e invisíveis
ZERO_WIDTH_CHARS = {
    "\u200B": "Zero-Width Space (U+200B)",
    "\u200C": "Zero-Width Non-Joiner (U+200C)",
    "\u200D": "Zero-Width Joiner (U+200D)",
    "\u200E": "Left-to-Right Mark (U+200E)",
    "\u200F": "Right-to-Left Mark (U+200F)",
    "\u2060": "Word Joiner (U+2060)",
    "\uFEFF": "Zero-Width No-Break Space / BOM (U+FEFF)",
    "\u180E": "Mongolian Vowel Separator (U+180E)",
}

# Espaços Unicode especiais
SPECIAL_SPACES = {
    "\u00A0": "Non-Breaking Space (U+00A0)",
    "\u2000": "En Quad (U+2000)",
    "\u2001": "Em Quad (U+2001)",
    "\u2002": "En Space (U+2002)",
    "\u2003": "Em Space (U+2003)",
    "\u2004": "Three-Per-Em Space (U+2004)",
    "\u2005": "Four-Per-Em Space (U+2005)",
    "\u2006": "Six-Per-Em Space (U+2006)",
    "\u2007": "Figure Space (U+2007)",
    "\u2008": "Punctuation Space (U+2008)",
    "\u2009": "Thin Space (U+2009)",
    "\u200A": "Hair Space (U+200A)",
    "\u202F": "Narrow No-Break Space (U+202F)",
    "\u205F": "Medium Mathematical Space (U+205F)",
    "\u3000": "Ideographic Space (U+3000)",
}

# Mapeamento de aspas e hífens tipográficos para ASCII
SMART_PUNCTUATION_MAP = {
    "\u2018": "'",  # Left single quotation mark
    "\u2019": "'",  # Right single quotation mark
    "\u201A": "'",  # Single low-9 quotation mark
    "\u201B": "'",  # Single high-reversed-9 quotation mark
    "\u201C": '"',  # Left double quotation mark
    "\u201D": '"',  # Right double quotation mark
    "\u201E": '"',  # Double low-9 quotation mark
    "\u201F": '"',  # Double high-reversed-9 quotation mark
    "\u00AB": '"',  # Left-pointing double angle quotation mark
    "\u00BB": '"',  # Right-pointing double angle quotation mark
    "\u2013": "-",  # En dash
    "\u2014": "--", # Em dash
    "\u2015": "--", # Horizontal bar
    "\u2026": "...",# Ellipsis
}

# Homóglifos frequentes (Cirílico/Grego -> Latino correspondente)
HOMOGLYPH_MAP = {
    "а": "a",  # U+0430 Cyrillic
    "А": "A",  # U+0410 Cyrillic
    "с": "c",  # U+0441 Cyrillic
    "С": "C",  # U+0421 Cyrillic
    "е": "e",  # U+0435 Cyrillic
    "Е": "E",  # U+0415 Cyrillic
    "і": "i",  # U+0456 Cyrillic
    "І": "I",  # U+0406 Cyrillic
    "ј": "j",  # U+0458 Cyrillic
    "Ј": "J",  # U+0408 Cyrillic
    "о": "o",  # U+043E Cyrillic
    "О": "O",  # U+041E Cyrillic
    "р": "p",  # U+0440 Cyrillic
    "Р": "P",  # U+0420 Cyrillic
    "ѕ": "s",  # U+0455 Cyrillic
    "Ѕ": "S",  # U+0405 Cyrillic
    "х": "x",  # U+0445 Cyrillic
    "Х": "X",  # U+0425 Cyrillic
    "у": "y",  # U+0443 Cyrillic
    "Ү": "Y",  # U+04AE Cyrillic
    "ο": "o",  # U+03BF Greek
    "Ο": "O",  # U+039F Greek
}


@dataclass(frozen=True)
class SuspiciousCharInfo:
    """Informações sobre um caractere suspeito encontrado no texto."""
    index: int
    char: str
    codepoint: str
    name: str
    category: str
    reason: str


def inspect_unicode_text(text: str) -> List[SuspiciousCharInfo]:
    """
    Analisa a string caractere por caractere identificando caracteres invisíveis,
    zero-width, pontuações tipográficas e potenciais homóglifos.
    """
    results: List[SuspiciousCharInfo] = []
    for idx, char in enumerate(text):
        cp = f"U+{ord(char):04X}"
        name = unicodedata.name(char, "UNKNOWN")
        cat = unicodedata.category(char)

        if char in ZERO_WIDTH_CHARS:
            results.append(SuspiciousCharInfo(
                index=idx,
                char=char,
                codepoint=cp,
                name=name,
                category=cat,
                reason="Caractere Invisível / Largura Zero"
            ))
        elif char in SPECIAL_SPACES:
            results.append(SuspiciousCharInfo(
                index=idx,
                char=char,
                codepoint=cp,
                name=name,
                category=cat,
                reason="Espaço Unicode Especial (NBSP/Espaço Atípico)"
            ))
        elif char in SMART_PUNCTUATION_MAP:
            results.append(SuspiciousCharInfo(
                index=idx,
                char=char,
                codepoint=cp,
                name=name,
                category=cat,
                reason="Aspa ou Pontuação Tipográfica"
            ))
        elif char in HOMOGLYPH_MAP:
            target = HOMOGLYPH_MAP[char]
            results.append(SuspiciousCharInfo(
                index=idx,
                char=char,
                codepoint=cp,
                name=name,
                category=cat,
                reason=f"Potencial Homóglifo (confunde-se com '{target}')"
            ))
        elif cat.startswith("C") and char not in ("\n", "\r", "\t"):
            results.append(SuspiciousCharInfo(
                index=idx,
                char=char,
                codepoint=cp,
                name=name,
                category=cat,
                reason=f"Caractere de Controle ({cat})"
            ))

    return results


def remove_zero_width_chars(text: str) -> str:
    """Remove todos os caracteres zero-width e marcadores de ordem de bytes."""
    return "".join(c for c in text if c not in ZERO_WIDTH_CHARS)


def normalize_spaces(text: str) -> str:
    """Substitui espaços especiais (como Non-Breaking Space) por espaços comuns ASCII."""
    return "".join(" " if c in SPECIAL_SPACES else c for c in text)


def replace_smart_quotes(text: str) -> str:
    """Substitui aspas curvas e hífens tipográficos por equivalentes padrão ASCII."""
    return "".join(SMART_PUNCTUATION_MAP.get(c, c) for c in text)


def replace_homoglyphs(text: str) -> str:
    """Substitui homóglifos cirílicos/gregos comuns pelos equivalentes latinos."""
    return "".join(HOMOGLYPH_MAP.get(c, c) for c in text)


def normalize_form(text: str, form: str = "NFC") -> str:
    """Aplica normalização canônica Unicode (NFC, NFD, NFKC, NFKD)."""
    if form.upper() not in ("NFC", "NFD", "NFKC", "NFKD"):
        form = "NFC"
    return unicodedata.normalize(form.upper(), text)


def sanitize_text(
    text: str,
    strip_zero_width: bool = True,
    norm_spaces: bool = True,
    fix_quotes: bool = True,
    replace_homoglyphs_flag: bool = False,
    normalization_form: Optional[str] = "NFC"
) -> str:
    """
    Higieniza o texto aplicando as opções selecionadas de limpeza.
    """
    res = text
    if strip_zero_width:
        res = remove_zero_width_chars(res)
    if norm_spaces:
        res = normalize_spaces(res)
    if fix_quotes:
        res = replace_smart_quotes(res)
    if replace_homoglyphs_flag:
        res = replace_homoglyphs(res)
    if normalization_form:
        res = normalize_form(res, normalization_form)
    return res
