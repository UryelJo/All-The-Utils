"""
Lógica pura para conversão e estilização de documentos Markdown para HTML.
"""
import re
from pathlib import Path
from typing import Optional

try:
    import markdown
except ImportError:
    markdown = None

HTML_STYLE_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI Variable", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            max-width: 860px;
            margin: 40px auto;
            padding: 0 24px;
            background-color: #ffffff;
        }}
        @media (prefers-color-scheme: dark) {{
            body {{
                background-color: #121212;
                color: #e0e0e0;
            }}
            pre, code {{
                background-color: #1e1e1e !important;
                color: #f0f0f0 !important;
            }}
            table th {{
                background-color: #242424 !important;
            }}
            table th, table td {{
                border-color: #333333 !important;
            }}
            blockquote {{
                border-left-color: #0078d4 !important;
                color: #aaaaaa !important;
            }}
            hr {{
                border-color: #333333 !important;
            }}
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 12px;
            font-weight: 600;
            line-height: 1.25;
        }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #e1e4e8; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #e1e4e8; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}
        p, ul, ol {{ margin-bottom: 16px; }}
        pre {{
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
            font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
            font-size: 13px;
        }}
        code {{
            background-color: rgba(27, 31, 35, 0.05);
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: "Cascadia Mono", Consolas, monospace;
            font-size: 85%;
        }}
        pre code {{ background-color: transparent; padding: 0; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}
        table th, table td {{
            padding: 8px 12px;
            border: 1px solid #d0d7de;
        }}
        table th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
        blockquote {{
            margin: 0 0 16px 0;
            padding: 0 1em;
            color: #57606a;
            border-left: 0.25em solid #0078d4;
        }}
        hr {{
            height: 0.25em;
            padding: 0;
            margin: 24px 0;
            background-color: #e1e4e8;
            border: 0;
        }}
    </style>
</head>
<body>
{body_content}
</body>
</html>
"""


def markdown_to_html(
    md_text: str,
    title: str = "Documento",
    full_html: bool = True
) -> str:
    """
    Converte texto Markdown para HTML estilizado.
    """
    if markdown:
        raw_html = markdown.markdown(
            md_text,
            extensions=["tables", "fenced_code", "nl2br"]
        )
    else:
        # Fallback leve caso a biblioteca markdown não esteja disponível
        raw_html = _simple_markdown_fallback(md_text)

    if not full_html:
        return raw_html

    return HTML_STYLE_TEMPLATE.format(
        title=title,
        body_content=raw_html
    )


def _simple_markdown_fallback(text: str) -> str:
    """Conversor básico para headers e parágrafos sem dependências."""
    lines = text.splitlines()
    html_lines = []
    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)
