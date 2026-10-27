"""
Testes de validação de efeito real para text.regex_tester.logic.
"""
import re
import pytest

from wintoolbox.tools.text.regex_tester.logic import (
    COMMON_REGEX_PATTERNS,
    RegexMatchItem,
    find_regex_matches,
    apply_regex_replace,
)


def test_find_regex_matches_with_groups_deterministic():
    pattern = r"(?P<user>[a-zA-Z0-9]+)@(?P<domain>[a-zA-Z0-9.]+)"
    text = "Emails: alice@test.com e bob@work.org"

    matches = find_regex_matches(pattern, text)
    assert len(matches) == 2

    m1 = matches[0]
    assert m1.full_match == "alice@test.com"
    assert m1.span == (8, 22)
    assert m1.groups["Grupo 1"] == "alice"
    assert m1.groups["Grupo 2"] == "test.com"
    assert m1.groups["Nome 'user'"] == "alice"
    assert m1.groups["Nome 'domain'"] == "test.com"

    m2 = matches[1]
    assert m2.full_match == "bob@work.org"


def test_find_regex_matches_flags_and_invalid():
    # Ignore case
    matches = find_regex_matches(r"windows", "WINDOWS 11", flags=re.IGNORECASE)
    assert len(matches) == 1
    assert matches[0].full_match == "WINDOWS"

    # Sintaxe inválida
    with pytest.raises(re.error):
        find_regex_matches(r"[a-z(", "texto")


def test_apply_regex_replace_deterministic():
    pattern = r"(\d{3})\.(\d{3})\.(\d{3})-(\d{2})"
    replacement = r"\1\2\3\4"
    text = "CPF: 123.456.789-00"

    res = apply_regex_replace(pattern, replacement, text)
    assert res == "CPF: 12345678900"


def test_common_regex_patterns_validity():
    # Todos os padrões da biblioteca pré-configurada devem compilar com sucesso
    for name, item in COMMON_REGEX_PATTERNS.items():
        pat = item["pattern"]
        compiled = re.compile(pat)
        assert compiled is not None
