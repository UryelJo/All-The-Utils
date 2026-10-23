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
from .logic import compute_diff_html

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
