"""
Testes unitários rigorosos para conversão de IDN Punycode e entidades HTML.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
import pytest
from wintoolbox.tools.encode.punycode_html.logic import (
    decode_html_entities,
    domain_to_punycode,
    encode_html_entities,
    punycode_to_domain,
)


def test_punycode_domains_roundtrip():
    """Valida conversão bidirecional exata de domínios com caracteres internacionais."""
    # Exemplo alemão clássico
    assert domain_to_punycode("münchen.de") == "xn--mnchen-3ya.de"
    assert punycode_to_domain("xn--mnchen-3ya.de") == "münchen.de"

    # Exemplo brasileiro com acento agudo
    assert domain_to_punycode("café.com.br") == "xn--caf-dma.com.br"
    assert punycode_to_domain("xn--caf-dma.com.br") == "café.com.br"

    # Domínio puramente ASCII deve permanecer inalterado
    assert domain_to_punycode("wintoolbox.local") == "wintoolbox.local"
    assert punycode_to_domain("wintoolbox.local") == "wintoolbox.local"


def test_punycode_full_url():
    """Valida conversão de URLs completas com protocolo e caminho."""
    url = "https://münchen.de/turismo?ref=1"
    puny_url = domain_to_punycode(url)
    assert puny_url == "https://xn--mnchen-3ya.de/turismo?ref=1"

    restored_url = punycode_to_domain(puny_url)
    assert restored_url == url


def test_html_entities_named():
    """Valida codificação e decodificação de entidades HTML nomeadas."""
    text = "5 < 10 & 20 > 15 \"aspas\" © 2026"
    encoded = encode_html_entities(text, mode="named")
    assert "&lt;" in encoded
    assert "&gt;" in encoded
    assert "&amp;" in encoded
    assert "&quot;" in encoded
    assert "&copy;" in encoded

    decoded = decode_html_entities(encoded)
    assert decoded == text


def test_html_entities_decimal_and_hex():
    """Valida codificação para entidades numéricas decimais e hexadecimais."""
    char = "©"
    dec_entity = encode_html_entities(char, mode="decimal")
    assert dec_entity == "&#169;"
    assert decode_html_entities(dec_entity) == "©"

    hex_entity = encode_html_entities(char, mode="hex")
    assert hex_entity == "&#xA9;"
    assert decode_html_entities(hex_entity) == "©"


def test_empty_and_passthrough():
    """Valida comportamento para strings vazias."""
    assert domain_to_punycode("") == ""
    assert punycode_to_domain("") == ""
    assert encode_html_entities("") == ""
    assert decode_html_entities("") == ""
