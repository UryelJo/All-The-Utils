"""
Lógica pura para codificação e decodificação avançada de entidades HTML e caracteres Unicode.
Suporta entidades nomeadas (&copy;), numéricas decimais (&#169;) e numéricas hexadecimais (&#xA9;),
além de catálogo de referência rápida para desenvolvedores.

Zero dependências de interface gráfica.
"""
import html
import html.entities
import re
from typing import Any, Dict, List, Optional

# Catálogo curado das entidades mais utilizadas
COMMON_ENTITIES: List[Dict[str, str]] = [
    {"char": "&", "name": "&amp;", "dec": "&#38;", "hex": "&#x26;", "desc": "E comercial / Ampersand"},
    {"char": "<", "name": "&lt;", "dec": "&#60;", "hex": "&#x3C;", "desc": "Menor que / Less than"},
    {"char": ">", "name": "&gt;", "dec": "&#62;", "hex": "&#x3E;", "desc": "Maior que / Greater than"},
    {"char": '"', "name": "&quot;", "dec": "&#34;", "hex": "&#x22;", "desc": "Aspas duplas"},
    {"char": "'", "name": "&apos;", "dec": "&#39;", "hex": "&#x27;", "desc": "Aspas simples / Apóstrofo"},
    {"char": " ", "name": "&nbsp;", "dec": "&#160;", "hex": "&#xA0;", "desc": "Espaço sem quebra (Non-breaking space)"},
    {"char": "©", "name": "&copy;", "dec": "&#169;", "hex": "&#xA9;", "desc": "Direitos autorais (Copyright)"},
    {"char": "®", "name": "&reg;", "dec": "&#174;", "hex": "&#xAE;", "desc": "Marca registrada"},
    {"char": "™", "name": "&trade;", "dec": "&#8482;", "hex": "&#x2122;", "desc": "Marca comercial (Trade Mark)"},
    {"char": "€", "name": "&euro;", "dec": "&#8364;", "hex": "&#x20AC;", "desc": "Símbolo do Euro"},
    {"char": "£", "name": "&pound;", "dec": "&#163;", "hex": "&#xA3;", "desc": "Libra esterlina"},
    {"char": "¥", "name": "&yen;", "dec": "&#165;", "hex": "&#xA5;", "desc": "Iene / Yuan"},
    {"char": "§", "name": "&sect;", "dec": "&#167;", "hex": "&#xA7;", "desc": "Parágrafo / Seção jurídica"},
    {"char": "°", "name": "&deg;", "dec": "&#176;", "hex": "&#xB0;", "desc": "Grau"},
    {"char": "±", "name": "&plusmn;", "dec": "&#177;", "hex": "&#xB1;", "desc": "Mais ou menos"},
    {"char": "×", "name": "&times;", "dec": "&#215;", "hex": "&#xD7;", "desc": "Multiplicação"},
    {"char": "÷", "name": "&divide;", "dec": "&#247;", "hex": "&#xF7;", "desc": "Divisão"},
    {"char": "—", "name": "&mdash;", "dec": "&#8212;", "hex": "&#x2014;", "desc": "Travessão (Em dash)"},
    {"char": "–", "name": "&ndash;", "dec": "&#8211;", "hex": "&#x2013;", "desc": "Meia-risca (En dash)"},
    {"char": "•", "name": "&bull;", "dec": "&#8226;", "hex": "&#x2022;", "desc": "Marcador de lista (Bullet)"},
    {"char": "…", "name": "&hellip;", "dec": "&#8230;", "hex": "&#x2026;", "desc": "Reticências horizontais"},
    {"char": "←", "name": "&larr;", "dec": "&#8592;", "hex": "&#x2190;", "desc": "Seta para esquerda"},
    {"char": "→", "name": "&rarr;", "dec": "&#8594;", "hex": "&#x2192;", "desc": "Seta para direita"},
    {"char": "↑", "name": "&uarr;", "dec": "&#8593;", "hex": "&#x2191;", "desc": "Seta para cima"},
    {"char": "↓", "name": "&darr;", "dec": "&#8595;", "hex": "&#x2193;", "desc": "Seta para baixo"},
]


# Mapa reverso de caractere para nome de entidade
_CHAR_TO_NAME = {chr(code): f"&{name};" for code, name in html.entities.codepoint2name.items()}
_HTML_RESERVED = {"&", "<", ">", '"', "'"}


def encode_html(
    text: str,
    mode: str = "named",
    only_reserved: bool = False,
) -> str:
    """
    Codifica texto em entidades HTML.
    
    :param text: Texto de entrada.
    :param mode: 'named' (&copy;), 'decimal' (&#169;) ou 'hex' (&#xA9;).
    :param only_reserved: Se True, codifica apenas os 5 caracteres reservados (&, <, >, ", ').
    """
    if not text:
        return ""

    mode = mode.lower().strip()
    res = []

    for char in text:
        is_reserved = char in _HTML_RESERVED
        code = ord(char)
        is_non_ascii = code > 127

        # Se only_reserved for True, ignora caracteres normais e não reservados
        if only_reserved:
            if not is_reserved:
                res.append(char)
                continue
        else:
            if not is_reserved and not is_non_ascii:
                res.append(char)
                continue

        # Codificação de acordo com o modo
        if mode == "decimal":
            res.append(f"&#{code};")
        elif mode == "hex":
            res.append(f"&#x{code:X};")
        else:  # 'named'
            # Se houver entidade nomeada conhecida, usa-a; senão cai para decimal
            if char in _CHAR_TO_NAME:
                res.append(_CHAR_TO_NAME[char])
            elif char == "'":
                res.append("&apos;")
            else:
                res.append(f"&#{code};")

    return "".join(res)


def decode_html(text: str) -> str:
    """
    Decodifica entidades HTML (nomeadas, decimais ou hexadecimais) para texto Unicode.
    """
    if not text:
        return ""
    # html.unescape lida de forma nativa e segura com named, dec e hex
    return html.unescape(text)


def filter_catalog(query: str) -> List[Dict[str, str]]:
    """
    Filtra o catálogo de entidades comuns por termo de busca.
    """
    q = query.lower().strip()
    if not q:
        return COMMON_ENTITIES

    return [
        item for item in COMMON_ENTITIES
        if q in item["char"].lower()
        or q in item["name"].lower()
        or q in item["dec"].lower()
        or q in item["hex"].lower()
        or q in item["desc"].lower()
    ]
