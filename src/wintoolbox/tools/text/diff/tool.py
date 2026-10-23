"""
Ferramenta: Comparador de Textos (Diff Visual Lado a Lado).
Permite comparar dois textos ou códigos e visualizar as diferenças linha a linha.
"""
import difflib
import html
from typing import Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register

def compute_diff_html(text_a: str, text_b: str, ignore_whitespace: bool = False, ignore_case: bool = False) -> Tuple[str, int, int, int]:
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

    final_html = f"<html><head><style>{css}</style></head><body><table>{''.join(rows_html)}</table></body></html>"
    return final_html, added, removed, equal

@register
class TextDiffTool(Tool):
    id = "text.diff"
    name = "Comparador de Textos (Diff)"
    category = "Texto e Redação"
    description = "Compara dois blocos de texto ou código lado a lado com realce visual de alterações"
    keywords = ["diff", "comparar", "texto", "codigo", "alteracoes", "linhas", "diferenca"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TextDiffView(self, parent)

class TextDiffView(QWidget):
    def __init__(self, tool: TextDiffTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        root_layout.addWidget(lbl_desc)

        # Editores Lado a Lado
        editors_layout = QHBoxLayout()
        editors_layout.setSpacing(12)

        # Lado A: Original
        col_a = QVBoxLayout()
        col_a.addWidget(QLabel("Texto Original (A):"))
        self.txt_a = QPlainTextEdit()
        self.txt_a.setPlaceholderText("Cole o texto original aqui...")
        self.txt_a.setFixedHeight(180)
        col_a.addWidget(self.txt_a)
        editors_layout.addLayout(col_a)

        # Lado B: Modificado
        col_b = QVBoxLayout()
        col_b.addWidget(QLabel("Texto Modificado (B):"))
        self.txt_b = QPlainTextEdit()
        self.txt_b.setPlaceholderText("Cole o texto modificado aqui...")
        self.txt_b.setFixedHeight(180)
        col_b.addWidget(self.txt_b)
        editors_layout.addLayout(col_b)

        root_layout.addLayout(editors_layout)

        # Barra de Opções e Ações
        bar_opts = QHBoxLayout()
        self.chk_whitespace = QCheckBox("Ignorar espaços nas bordas")
        bar_opts.addWidget(self.chk_whitespace)

        self.chk_case = QCheckBox("Ignorar maiúsculas/minúsculas")
        bar_opts.addWidget(self.chk_case)

        bar_opts.addSpacing(16)
        self.btn_compare = QPushButton("Comparar Textos")
        self.btn_compare.setProperty("class", "primary")
        self.btn_compare.setFixedHeight(34)
        self.btn_compare.clicked.connect(self._run_diff)
        bar_opts.addWidget(self.btn_compare)

        self.btn_swap = QPushButton("Inverter Lados (A ↔ B)")
        self.btn_swap.setFixedHeight(34)
        self.btn_swap.clicked.connect(self._swap_texts)
        bar_opts.addWidget(self.btn_swap)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.setFixedHeight(34)
        self.btn_clear.clicked.connect(self._clear_all)
        bar_opts.addWidget(self.btn_clear)

        bar_opts.addStretch()

        self.lbl_stats = QLabel("Nenhuma comparação executada.")
        self.lbl_stats.setProperty("class", "secondary")
        bar_opts.addWidget(self.lbl_stats)

        root_layout.addLayout(bar_opts)

        # Visualizador de Diff (HTML)
        self.diff_view = QTextBrowser()
        self.diff_view.setOpenExternalLinks(False)
        self.diff_view.setStyleSheet("border: 1px solid #333; border-radius: 4px;")
        root_layout.addWidget(self.diff_view, stretch=1)

    def _run_diff(self):
        text_a = self.txt_a.toPlainText()
        text_b = self.txt_b.toPlainText()

        diff_html, added, removed, equal = compute_diff_html(
            text_a,
            text_b,
            ignore_whitespace=self.chk_whitespace.isChecked(),
            ignore_case=self.chk_case.isChecked()
        )
        self.diff_view.setHtml(diff_html)
        self.lbl_stats.setText(f"Diferenças: +{added} inserções, -{removed} remoções, {equal} inalteradas")

    def _swap_texts(self):
        a = self.txt_a.toPlainText()
        b = self.txt_b.toPlainText()
        self.txt_a.setPlainText(b)
        self.txt_b.setPlainText(a)
        self._run_diff()

    def _clear_all(self):
        self.txt_a.clear()
        self.txt_b.clear()
        self.diff_view.clear()
        self.lbl_stats.setText("Campos limpos.")
