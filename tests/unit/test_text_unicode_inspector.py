"""
Testes unitários rigorosos para a lógica de inspeção e higienização Unicode.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
import unicodedata
import pytest
from wintoolbox.tools.text.unicode_inspector.logic import (
    inspect_unicode_text,
    normalize_form,
    normalize_spaces,
    remove_zero_width_chars,
    replace_homoglyphs,
    replace_smart_quotes,
    sanitize_text,
)


def test_zero_width_and_bom_removal():
    """Valida remoção determinística de caracteres invisíveis e de largura zero."""
    dirty = "sen\u200Bha\u200Cse\u200Dcre\uFEFFta"
    assert len(dirty) == 16
    cleaned = remove_zero_width_chars(dirty)
    assert cleaned == "senhasecreta"
    assert len(cleaned) == 12


def test_special_spaces_and_quotes():
    """Valida normalização de NBSP e substituição de aspas curvas/tipográficas."""
    text_spaces = "Valor:\u00A0R$ 100,00\u2002total."
    norm_sp = normalize_spaces(text_spaces)
    assert norm_sp == "Valor: R$ 100,00 total."

    text_quotes = "“Olá, ‘Mundo’!”"
    ascii_quotes = replace_smart_quotes(text_quotes)
    assert ascii_quotes == '"Olá, \'Mundo\'!"'


def test_homoglyphs_detection_and_replacement():
    """Valida detecção e substituição de homóglifos cirílicos em nomes e domínios."""
    # O domínio abaixo possui 'а' cirílico (U+0430) em vez de 'a' latino (U+0061)
    cyrillic_a = "\u0430"
    phishing_domain = f"p{cyrillic_a}yp{cyrillic_a}l.com"
    
    issues = inspect_unicode_text(phishing_domain)
    assert len(issues) == 2
    assert issues[0].codepoint == "U+0430"
    assert "Homóglifo" in issues[0].reason

    clean_domain = replace_homoglyphs(phishing_domain)
    assert clean_domain == "paypal.com"
    # Agora só contém caracteres ASCII latinos
    assert all(ord(c) < 128 for c in clean_domain)


def test_canonical_normalization():
    """Valida normalização canônica Unicode NFC e NFD."""
    # 'ç' em NFC (1 caractere composto U+00E7) vs NFD ('c' + diacrítico combinante U+0327)
    nfc_str = "maçã"
    nfd_str = unicodedata.normalize("NFD", nfc_str)
    assert len(nfc_str) == 4
    assert len(nfd_str) == 6  # 'c'+cedilha, 'a'+til

    # Normalização para NFC deve retornar a forma compacta com exatamente 4 caracteres
    restored_nfc = normalize_form(nfd_str, "NFC")
    assert restored_nfc == "maçã"
    assert len(restored_nfc) == 4


def test_sanitize_all_integration():
    """Valida sanitização completa com múltiplas opções ligadas simultaneamente."""
    sample = "“Atenção:\u200B\u00A0p\u0430ssword”"
    res = sanitize_text(
        sample,
        strip_zero_width=True,
        norm_spaces=True,
        fix_quotes=True,
        replace_homoglyphs_flag=True,
        normalization_form="NFC"
    )
    assert res == '"Atenção: password"'
