"""
Lógica pura para comparação e cálculo de diferenças (Diff) entre textos.
"""
import difflib
import html
from typing import Tuple


def compute_diff_html(
    text_a: str,
    text_b: str,
    ignore_whitespace: bool = False,
    ignore_case: bool = False
) -> Tuple[str, int, int, int]:
    """
    Gera o relatório visual de diferenças em HTML.
    Retorna (html_diff, total_adicoes, total_remocoes, total_iguais).
    """
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    comp_a = lines_a
    comp_b = lines_b

    if ignore_whitespace:
        comp_a = [l.strip() for l in comp_a]
        comp_b = [l.strip() for l in comp_b]
    if ignore_case:
        comp_a = [l.lower() for l in comp_a]
        comp_b = [l.lower() for l in comp_b]

    matcher = difflib.SequenceMatcher(None, comp_a, comp_b)
    opcodes = matcher.get_opcodes()

    added = 0
    removed = 0
    equal = 0

    rows_html = []
    line_no_a = 1
    line_no_b = 1

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for idx in range(i1, i2):
                content = html.escape(lines_a[idx])
                rows_html.append(
                    f"<tr><td class='lineno'>{line_no_a}</td><td class='lineno'>{line_no_b}</td>"
                    f"<td class='sign'> </td><td class='content'>{content}</td></tr>"
                )
                line_no_a += 1
                line_no_b += 1
                equal += 1
        elif tag == "delete":
            for idx in range(i1, i2):
                content = html.escape(lines_a[idx])
                rows_html.append(
                    f"<tr class='del'><td class='lineno'>{line_no_a}</td><td class='lineno'>-</td>"
                    f"<td class='sign'>-</td><td class='content'>{content}</td></tr>"
                )
                line_no_a += 1
                removed += 1
        elif tag == "insert":
            for idx in range(j1, j2):
                content = html.escape(lines_b[idx])
                rows_html.append(
                    f"<tr class='ins'><td class='lineno'>-</td><td class='lineno'>{line_no_b}</td>"
                    f"<td class='sign'>+</td><td class='content'>{content}</td></tr>"
                )
                line_no_b += 1
                added += 1
        elif tag == "replace":
            for idx in range(i1, i2):
                content = html.escape(lines_a[idx])
                rows_html.append(
                    f"<tr class='del'><td class='lineno'>{line_no_a}</td><td class='lineno'>-</td>"
                    f"<td class='sign'>-</td><td class='content'>{content}</td></tr>"
                )
                line_no_a += 1
                removed += 1
            for idx in range(j1, j2):
                content = html.escape(lines_b[idx])
                rows_html.append(
                    f"<tr class='ins'><td class='lineno'>-</td><td class='lineno'>{line_no_b}</td>"
                    f"<td class='sign'>+</td><td class='content'>{content}</td></tr>"
                )
                line_no_b += 1
                added += 1

    css = """
    body { font-family: 'Consolas', 'Segoe UI Mono', monospace; font-size: 13px; color: #d4d4d4; background: #181818; margin: 0; padding: 8px; }
    table { width: 100%; border-collapse: collapse; }
    td { padding: 2px 6px; white-space: pre-wrap; font-family: inherit; }
    .lineno { width: 45px; text-align: right; color: #6e7681; user-select: none; border-right: 1px solid #333; }
    .sign { width: 16px; text-align: center; font-weight: bold; }
    .content { word-break: break-all; }
    tr.del { background: rgba(248, 81, 73, 0.18); color: #ffa198; }
    tr.ins { background: rgba(46, 160, 67, 0.22); color: #7ee787; }
    """

    doc_html = f"<html><head><style>{css}</style></head><body><table>{''.join(rows_html)}</table></body></html>"
    return doc_html, added, removed, equal
