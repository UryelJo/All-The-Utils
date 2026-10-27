"""
Lógica pura para conversão de Domínios Internacionalizados (IDN / Punycode RFC 3492/5891)
e Codificação/Decodificação de Entidades de Caracteres HTML.

Suporta:
- Conversão bidirecional de domínios e URLs completas (Unicode <-> Punycode 'xn--...')
- Codificação de HTML entities (Entidades nomeadas, numéricas decimais e numéricas hexadecimais)
- Decodificação de qualquer entidade HTML (nomeada ou numérica) para caractere Unicode nativo

Isolado de qualquer biblioteca de interface gráfica.
"""
import html
import html.entities
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse


def domain_to_punycode(domain_or_url: str) -> str:
    """
    Converte um domínio ou URL contendo caracteres Unicode para formato Punycode (ASCII compatível).
    Ex: 'münchen.de' -> 'xn--mnchen-3ya.de'
    """
    s = domain_or_url.strip()
    if not s:
        return ""

    # Se for uma URL completa com protocolo
    if "://" in s:
        parsed = urlparse(s)
        try:
            # host pode conter porta
            hostname = parsed.hostname or ""
            puny_host = hostname.encode("idna").decode("ascii")
            netloc = puny_host
            if parsed.port:
                netloc = f"{puny_host}:{parsed.port}"
            if parsed.username:
                userinfo = parsed.username
                if parsed.password:
                    userinfo += f":{parsed.password}"
                netloc = f"{userinfo}@{netloc}"
            return urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
        except Exception:
            pass

    # Conversão de domínio puro
    try:
        return s.encode("idna").decode("ascii")
    except Exception as e:
        return f"Erro ao converter para Punycode: {e}"


def punycode_to_domain(punycode_domain_or_url: str) -> str:
    """
    Converte um domínio ou URL em formato Punycode ('xn--...') de volta para Unicode amigável.
    Ex: 'xn--mnchen-3ya.de' -> 'münchen.de'
    """
    s = punycode_domain_or_url.strip()
    if not s:
        return ""

    if "://" in s:
        parsed = urlparse(s)
        try:
            hostname = parsed.hostname or ""
            unicode_host = hostname.encode("ascii").decode("idna")
            netloc = unicode_host
            if parsed.port:
                netloc = f"{unicode_host}:{parsed.port}"
            if parsed.username:
                userinfo = parsed.username
                if parsed.password:
                    userinfo += f":{parsed.password}"
                netloc = f"{userinfo}@{netloc}"
            return urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
        except Exception:
            pass

    try:
        return s.encode("ascii").decode("idna")
    except Exception as e:
        return f"Erro ao decodificar Punycode: {e}"


def encode_html_entities(text: str, mode: str = "named") -> str:
    """
    Codifica caracteres não-ASCII e reservados em entidades HTML.
    Modos:
    - 'named': Entidades nomeadas (ex: &copy;, &lt;)
    - 'decimal': Entidades numéricas decimais (ex: &#169;, &#60;)
    - 'hex': Entidades numéricas hexadecimais (ex: &#xA9;, &#x3C;)
    """
    if not text:
        return ""

    res = []
    for char in text:
        code = ord(char)
        # Caracteres ASCII seguros básicos permanecem inalterados, exceto reservados HTML (& < > " ')
        if char == "&":
            res.append("&amp;" if mode == "named" else f"&#{code};" if mode == "decimal" else f"&#x{code:X};")
        elif char == "<":
            res.append("&lt;" if mode == "named" else f"&#{code};" if mode == "decimal" else f"&#x{code:X};")
        elif char == ">":
            res.append("&gt;" if mode == "named" else f"&#{code};" if mode == "decimal" else f"&#x{code:X};")
        elif char == '"':
            res.append("&quot;" if mode == "named" else f"&#{code};" if mode == "decimal" else f"&#x{code:X};")
        elif char == "'":
            res.append("&#39;" if mode in ("named", "decimal") else f"&#x{code:X};")
        elif code > 127:
            if mode == "named" and code in html.entities.codepoint2name:
                res.append(f"&{html.entities.codepoint2name[code]};")
            elif mode == "hex":
                res.append(f"&#x{code:X};")
            else:
                res.append(f"&#{code};")
        else:
            res.append(char)

    return "".join(res)


def decode_html_entities(text: str) -> str:
    """
    Decodifica entidades HTML (nomeadas, decimais ou hexadecimais) de volta para Unicode puro.
    """
    if not text:
        return ""
    return html.unescape(text)
