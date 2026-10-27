"""
Testes de validação de efeito real para text.markdown_editor.logic.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.text.markdown_editor.logic import (
    render_markdown_to_html,
    extract_markdown_headings,
    export_markdown_file,
)


def test_render_markdown_to_html_elements_deterministic():
    sample_md = (
        "# Título do Artigo\n\n"
        "Este texto contém **negrito** e *itálico*.\n\n"
        "```python\ndef soma(a, b):\n    return a + b\n```\n\n"
        "| Col1 | Col2 |\n"
        "| :--- | :--- |\n"
        "| 100  | 200  |\n"
    )

    html_code = render_markdown_to_html(sample_md, include_css=True)

    assert '<h1 id="titulo-do-artigo">Título do Artigo</h1>' in html_code
    assert "<strong>negrito</strong>" in html_code
    assert "<em>itálico</em>" in html_code
    assert "<pre><code" in html_code
    assert "<table>" in html_code
    assert ">100</td>" in html_code
    assert "<style>" in html_code


def test_extract_markdown_headings_deterministic():
    sample_md = """
    # Nível 1
    Texto
    ## Nível 2
    Texto
    ### Nível 3 Subitem
    """
    headings = extract_markdown_headings(sample_md)
    assert len(headings) == 3
    assert headings[0] == (1, "Nível 1")
    assert headings[1] == (2, "Nível 2")
    assert headings[2] == (3, "Nível 3 Subitem")


def test_export_markdown_file_black_box(tmp_path: Path):
    doc_text = "# Documento de Teste\nConteúdo"
    html_target = tmp_path / "saida.html"

    res_path = export_markdown_file(doc_text, html_target, format_type="html")
    assert res_path.is_file()
    assert res_path == html_target

    read_content = res_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in read_content
    assert '<h1 id="documento-de-teste">Documento de Teste</h1>' in read_content
