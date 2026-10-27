"""
Lógica pura para edição e renderização de Markdown para HTML.

Suporta tabelas GFM, blocos de código delimitados (fenced code),
tabela de conteúdos (TOC) e folha de estilos tipográfica limpa estilo GitHub.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import markdown

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("text.markdown_editor.logic")

GITHUB_MARKDOWN_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    color: #24292f;
    background-color: #ffffff;
    margin: 0;
    padding: 16px;
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
}
h1 { font-size: 1.8em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3em; }
h2 { font-size: 1.4em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3em; }
h3 { font-size: 1.2em; }
code {
    padding: 0.2em 0.4em;
    margin: 0;
    font-size: 85%;
    background-color: #f6f8fa;
    border-radius: 6px;
    font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace;
}
pre {
    padding: 14px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    background-color: #f6f8fa;
    border-radius: 6px;
    border: 1px solid #d0d7de;
}
pre code {
    padding: 0;
    background-color: transparent;
}
blockquote {
    padding: 0 1em;
    color: #57606a;
    border-left: 0.25em solid #d0d7de;
    margin: 0 0 16px 0;
}
table {
    border-spacing: 0;
    border-collapse: collapse;
    margin-bottom: 16px;
    width: 100%;
}
table th, table td {
    padding: 6px 13px;
    border: 1px solid #d0d7de;
}
table th {
    font-weight: 600;
    background-color: #f6f8fa;
}
table tr:nth-child(2n) {
    background-color: #f6f8fa;
}
hr {
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #d0d7de;
    border: 0;
}
ul, ol {
    padding-left: 2em;
    margin-bottom: 16px;
}
"""


def render_markdown_to_html(md_text: str, include_css: bool = True) -> str:
    """
    Converte texto Markdown para HTML completo com suporte a tabelas e blocos de código.
    """
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br", "toc", "sane_lists"]
    )

    if not include_css:
        return html_body

    return (
        f"<!DOCTYPE html>\n"
        f"<html>\n<head>\n"
        f'<meta charset="utf-8">\n'
        f"<style>\n{GITHUB_MARKDOWN_CSS}\n</style>\n"
        f"</head>\n<body>\n"
        f"{html_body}\n"
        f"</body>\n</html>"
    )


def extract_markdown_headings(md_text: str) -> List[Tuple[int, str]]:
    """
    Extrai lista de cabeçalhos (nível, título) do documento.
    """
    headings: List[Tuple[int, str]] = []
    for line in md_text.splitlines():
        line_clean = line.strip()
        m = re.match(r"^(#{1,6})\s+(.+)$", line_clean)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            headings.append((level, title))
    return headings


def export_markdown_file(md_text: str, output_path: Path, format_type: str = "html") -> Path:
    """
    Exporta o documento para arquivo (.html ou .md conforme a extensão).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = format_type.lower().lstrip(".")

    if fmt == "html" or output_path.suffix.lower() == ".html":
        content = render_markdown_to_html(md_text, include_css=True)
        output_path.write_text(content, encoding="utf-8")
    else:
        output_path.write_text(md_text, encoding="utf-8")

    return output_path
