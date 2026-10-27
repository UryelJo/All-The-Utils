"""
Testes de validação de efeito real para text.diff_visual.logic.
"""
import pytest
from wintoolbox.tools.text.diff_visual.logic import (
    compute_inline_char_diff,
    generate_diff_table_html,
)


def test_compute_inline_char_diff_deterministic():
    old_line = "const taxa = 10;"
    new_line = "const taxa = 25;"

    h_old, h_new = compute_inline_char_diff(old_line, new_line)

    # Apenas a parte alterada ("10" e "25") deve estar dentro da tag <mark>
    assert "<mark" in h_old
    assert "10</mark>" in h_old
    assert "const taxa = " in h_old

    assert "<mark" in h_new
    assert "25</mark>" in h_new
    assert "const taxa = " in h_new


def test_generate_diff_table_html_side_by_side_structure():
    t_a = "linha 1\nlinha original 2\nlinha 3"
    t_b = "linha 1\nlinha modificada 2\nlinha 3"

    html_out = generate_diff_table_html(t_a, t_b, side_by_side=True)

    assert "<table>" in html_out
    assert "</table>" in html_out
    assert "del-bg" in html_out
    assert "add-bg" in html_out
    assert "<mark" in html_out


def test_generate_diff_table_html_unified():
    t_a = "versao 1"
    t_b = "versao 2"

    html_unified = generate_diff_table_html(t_a, t_b, side_by_side=False)

    assert "del-sign" in html_unified
    assert "add-sign" in html_unified
    assert "-" in html_unified
    assert "+" in html_unified


def test_generate_diff_table_html_identical():
    t_same = "codigo identico\nsem alteracoes"
    html_same = generate_diff_table_html(t_same, t_same)

    assert 'class="code del-bg"' not in html_same
    assert 'class="code add-bg"' not in html_same
    assert "<mark" not in html_same
