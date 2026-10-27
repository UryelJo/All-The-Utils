"""
Testes de validação de efeito real para text.lorem_advanced.logic.
"""
import pytest
from wintoolbox.tools.text.lorem_advanced.logic import (
    THEME_VOCABULARY,
    generate_lorem_text,
)


def test_generate_lorem_exact_words_count():
    txt = generate_lorem_text(theme="corporativo", unit="words", count=30, start_with_lead=False)
    words = txt.strip(".").split()
    assert len(words) == 30


def test_generate_lorem_sentences_and_html_format():
    html_res = generate_lorem_text(
        theme="juridico",
        unit="sentences",
        count=4,
        output_format="html",
        start_with_lead=True
    )
    assert "<p>" in html_res
    assert "</p>" in html_res
    assert html_res.count("<p>") == 4
    # Deve conter termo característico do tema jurídico
    assert "venia" in html_res.lower() or "tutela" in html_res.lower() or "nexo" in html_res.lower()


def test_generate_lorem_paragraphs_markdown():
    md_res = generate_lorem_text(
        theme="sci_fi",
        unit="paragraphs",
        count=3,
        output_format="markdown",
        start_with_lead=True
    )
    paragraphs = md_res.split("\n\n")
    assert len(paragraphs) == 3
    for p in paragraphs:
        assert p.startswith("> ")


def test_all_themes_generate_coherent_text():
    for theme_name in THEME_VOCABULARY:
        res = generate_lorem_text(theme=theme_name, unit="sentences", count=2)
        assert len(res) > 20
        assert res.endswith(".")
