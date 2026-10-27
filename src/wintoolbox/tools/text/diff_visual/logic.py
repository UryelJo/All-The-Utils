"""
Lógica pura para comparação visual de textos com realce inline de caracteres (estilo GitHub Diff).

Calcula diferenças linha a linha e intra-linha utilizando difflib.SequenceMatcher,
destacando caracteres específicos inseridos, modificados ou removidos.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import difflib
import html
from typing import Any, Dict, List, Optional, Tuple


def compute_inline_char_diff(old_line: str, new_line: str) -> Tuple[str, str]:
    """
    Compara duas linhas alteradas e gera strings HTML com as diferenças de caracteres destacadas em tags <mark>.
    """
    matcher = difflib.SequenceMatcher(None, old_line, new_line)
    old_html_parts: List[str] = []
    new_html_parts: List[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        sub_old = html.escape(old_line[i1:i2])
        sub_new = html.escape(new_line[j1:j2])

        if tag == "equal":
            old_html_parts.append(sub_old)
            new_html_parts.append(sub_new)
        elif tag == "delete":
            old_html_parts.append(f'<mark style="background-color: #f87171; border-radius: 2px;">{sub_old}</mark>')
        elif tag == "insert":
            new_html_parts.append(f'<mark style="background-color: #4ade80; border-radius: 2px;">{sub_new}</mark>')
        elif tag == "replace":
            old_html_parts.append(f'<mark style="background-color: #fca5a5; border-radius: 2px;">{sub_old}</mark>')
            new_html_parts.append(f'<mark style="background-color: #86efac; border-radius: 2px;">{sub_new}</mark>')

    return "".join(old_html_parts), "".join(new_html_parts)


def generate_diff_table_html(text_a: str, text_b: str, side_by_side: bool = True) -> str:
    """
    Gera tabela HTML completa estilo GitHub Diff com numeração de linha e destaque inline.
    """
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)

    rows_html: List[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                idx_a = i1 + offset + 1
                idx_b = j1 + offset + 1
                line_content = html.escape(lines_a[i1 + offset])
                if side_by_side:
                    rows_html.append(
                        f'<tr><td class="num">{idx_a}</td><td class="code">{line_content}</td>'
                        f'<td class="num">{idx_b}</td><td class="code">{line_content}</td></tr>'
                    )
                else:
                    rows_html.append(
                        f'<tr><td class="num">{idx_a}</td><td class="num">{idx_b}</td><td class="sign"> </td><td class="code">{line_content}</td></tr>'
                    )

        elif tag == "replace":
            # Realce inline de caracteres para linhas alteradas
            count = max(i2 - i1, j2 - j1)
            for offset in range(count):
                idx_a = (i1 + offset + 1) if (i1 + offset < i2) else ""
                idx_b = (j1 + offset + 1) if (j1 + offset < j2) else ""

                val_a = lines_a[i1 + offset] if (i1 + offset < i2) else None
                val_b = lines_b[j1 + offset] if (j1 + offset < j2) else None

                if val_a is not None and val_b is not None:
                    h_a, h_b = compute_inline_char_diff(val_a, val_b)
                elif val_a is not None:
                    h_a = html.escape(val_a)
                    h_b = ""
                else:
                    h_a = ""
                    h_b = html.escape(val_b)

                if side_by_side:
                    rows_html.append(
                        f'<tr class="diff-row">'
                        f'<td class="num del-num">{idx_a}</td><td class="code del-bg">{h_a}</td>'
                        f'<td class="num add-num">{idx_b}</td><td class="code add-bg">{h_b}</td>'
                        f'</tr>'
                    )
                else:
                    if val_a is not None:
                        rows_html.append(
                            f'<tr class="del-row"><td class="num del-num">{idx_a}</td><td class="num"></td><td class="sign del-sign">-</td><td class="code del-bg">{html.escape(val_a)}</td></tr>'
                        )
                    if val_b is not None:
                        rows_html.append(
                            f'<tr class="add-row"><td class="num"></td><td class="num add-num">{idx_b}</td><td class="sign add-sign">+</td><td class="code add-bg">{html.escape(val_b)}</td></tr>'
                        )

        elif tag == "delete":
            for offset in range(i2 - i1):
                idx_a = i1 + offset + 1
                h_a = html.escape(lines_a[i1 + offset])
                if side_by_side:
                    rows_html.append(
                        f'<tr class="diff-row"><td class="num del-num">{idx_a}</td><td class="code del-bg">{h_a}</td>'
                        f'<td class="num"></td><td class="code"></td></tr>'
                    )
                else:
                    rows_html.append(
                        f'<tr class="del-row"><td class="num del-num">{idx_a}</td><td class="num"></td><td class="sign del-sign">-</td><td class="code del-bg">{h_a}</td></tr>'
                    )

        elif tag == "insert":
            for offset in range(j2 - j1):
                idx_b = j1 + offset + 1
                h_b = html.escape(lines_b[j1 + offset])
                if side_by_side:
                    rows_html.append(
                        f'<tr class="diff-row"><td class="num"></td><td class="code"></td>'
                        f'<td class="num add-num">{idx_b}</td><td class="code add-bg">{h_b}</td></tr>'
                    )
                else:
                    rows_html.append(
                        f'<tr class="add-row"><td class="num"></td><td class="num add-num">{idx_b}</td><td class="sign add-sign">+</td><td class="code add-bg">{h_b}</td></tr>'
                    )

    css = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; margin: 0; padding: 10px; font-size: 12px; background: #ffffff; color: #1e293b; }
        table { width: 100%; border-collapse: collapse; font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace; }
        td { padding: 2px 8px; vertical-align: top; white-space: pre-wrap; word-break: break-all; }
        .num { width: 40px; text-align: right; color: #94a3b8; user-select: none; border-right: 1px solid #e2e8f0; font-size: 11px; }
        .del-bg { background-color: #fee2e2; }
        .add-bg { background-color: #dcfce7; }
        .del-num { background-color: #fecaca; color: #b91c1c; }
        .add-num { background-color: #bbf7d0; color: #15803d; }
        .sign { width: 20px; text-align: center; font-weight: bold; }
        .del-sign { color: #dc2626; }
        .add-sign { color: #16a34a; }
    </style>
    """

    return f"<!DOCTYPE html><html><head>{css}</head><body><table>{''.join(rows_html)}</table></body></html>"
