"""
Ferramenta: Comparador Visual com Realce Inline de Caracteres (Diff Visual).
Exibe alterações lado a lado estilo GitHub com destaque de caracteres modificados.
"""
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSplitter,
    QTextBrowser, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.diff_visual.logic import generate_diff_table_html


@register
class VisualDiffTool(Tool):
    id = "text.diff_visual"
    name = "Comparador Visual com Realce Inline"
    category = "Texto e Redação"
    description = "Compare dois textos ou códigos lado a lado com realce visual detalhado de caracteres inseridos e removidos"
    keywords = ["diff", "comparar", "inline", "github diff", "alteracoes", "revisao", "codigo"]

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._render_diff)

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra de Controles Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        top_bar.addWidget(QLabel("Visualização:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Lado a Lado (Split)", "Unificado (Unified)"])
        self.cmb_mode.currentTextChanged.connect(self._schedule_render)
        top_bar.addWidget(self.cmb_mode)

        self.btn_swap = QPushButton("Inverter Lados (A ⇄ B)")
        self.btn_swap.clicked.connect(self._swap_texts)
        top_bar.addWidget(self.btn_swap)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.clicked.connect(self._clear_all)
        top_bar.addWidget(self.btn_clear)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Splitter Vertical: Entradas e Resultado
        v_splitter = QSplitter(Qt.Vertical)

        # Editores Lado a Lado
        inputs_widget = QWidget()
        inputs_layout = QHBoxLayout(inputs_widget)
        inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_layout.setSpacing(10)

        # Lado A
        box_a = QVBoxLayout()
        box_a.addWidget(QLabel("<b>Texto Original (A):</b>"))
        self.txt_a = QPlainTextEdit()
        self.txt_a.setPlaceholderText("Cole ou digite o texto original...")
        self.txt_a.setPlainText("const value = 100;\nconsole.log('Total:', value);\nfunction teste() {\n    return true;\n}")
        self.txt_a.textChanged.connect(self._schedule_render)
        box_a.addWidget(self.txt_a)
        inputs_layout.addLayout(box_a)

        # Lado B
        box_b = QVBoxLayout()
        box_b.addWidget(QLabel("<b>Texto Modificado (B):</b>"))
        self.txt_b = QPlainTextEdit()
        self.txt_b.setPlaceholderText("Cole ou digite o texto modificado...")
        self.txt_b.setPlainText("const value = 250;\nconsole.log('Total Final:', value);\nfunction teste() {\n    return false;\n}")
        self.txt_b.textChanged.connect(self._schedule_render)
        box_b.addWidget(self.txt_b)
        inputs_layout.addLayout(box_b)

        v_splitter.addWidget(inputs_widget)

        # Visualizador HTML
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        viewer_layout.setContentsMargins(0, 8, 0, 0)
        viewer_layout.addWidget(QLabel("<b>Diferenças Detectadas com Realce de Caracteres:</b>"))

        self.browser = QTextBrowser()
        self.browser.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 6px;")
        viewer_layout.addWidget(self.browser)
        v_splitter.addWidget(viewer_widget)

        v_splitter.setSizes([200, 350])
        main_layout.addWidget(v_splitter)

        self._render_diff()
        return container

    def _schedule_render(self) -> None:
        self._debounce_timer.start()

    def _render_diff(self) -> None:
        t_a = self.txt_a.toPlainText()
        t_b = self.txt_b.toPlainText()
        side_by_side = "Lado a Lado" in self.cmb_mode.currentText()

        html_content = generate_diff_table_html(t_a, t_b, side_by_side=side_by_side)
        self.browser.setHtml(html_content)

    def _swap_texts(self) -> None:
        a = self.txt_a.toPlainText()
        b = self.txt_b.toPlainText()
        self.txt_a.setPlainText(b)
        self.txt_b.setPlainText(a)

    def _clear_all(self) -> None:
        self.txt_a.clear()
        self.txt_b.clear()

    build_ui = build_view
