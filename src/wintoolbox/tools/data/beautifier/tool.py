"""
Ferramenta: Formatador e Minificador de Dados (JSON, XML, SQL).
Embeleza ou compacta código e dados estruturados em tempo real.
"""
import json
import re
import xml.dom.minidom
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from .logic import beautify_code, minify_code

@register
class DataBeautifierTool(Tool):
    id = "data.beautifier"
    name = "Formatador e Minificador (JSON/XML/SQL)"
    category = "Dados e Estruturas"
    description = "Embeleza ou minifica código e estruturas de dados em JSON, XML e SQL"
    keywords = ["formatar", "minificar", "json", "xml", "sql", "beautify", "indentar", "compactar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DataBeautifierView(self, parent)

class DataBeautifierView(QWidget):
    def __init__(self, tool: DataBeautifierTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Opções de Formatação
        card_cfg = QFrame()
        card_cfg.setProperty("class", "card")
        l_cfg = QHBoxLayout(card_cfg)
        l_cfg.setSpacing(12)

        l_cfg.addWidget(QLabel("Linguagem / Formato:"))
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["JSON", "XML", "SQL"])
        l_cfg.addWidget(self.cmb_lang)

        l_cfg.addWidget(QLabel("Identação:"))
        self.cmb_indent = QComboBox()
        self.cmb_indent.addItems(["2 espaços", "4 espaços"])
        l_cfg.addWidget(self.cmb_indent)

        self.btn_beautify = QPushButton("Formatar (Beautify)")
        self.btn_beautify.setProperty("class", "primary")
        self.btn_beautify.clicked.connect(self._do_beautify)
        l_cfg.addWidget(self.btn_beautify)

        self.btn_minify = QPushButton("Minificar (Compactar)")
        self.btn_minify.clicked.connect(self._do_minify)
        l_cfg.addWidget(self.btn_minify)

        l_cfg.addStretch()

        self.btn_swap = QPushButton("Inverter para Entrada")
        self.btn_swap.clicked.connect(self._swap_texts)
        l_cfg.addWidget(self.btn_swap)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.clicked.connect(self._clear)
        l_cfg.addWidget(self.btn_clear)

        layout.addWidget(card_cfg)

        # Editores Lado a Lado
        col_editors = QHBoxLayout()
        col_editors.setSpacing(12)

        # Lado 1: Entrada
        col_in = QVBoxLayout()
        col_in.addWidget(QLabel("Código / Dado Original:"))
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Cole o JSON, XML ou consulta SQL aqui...")
        self.txt_input.setPlainText('{"nome":"WinToolbox","versao":1.0,"recursos":["lote","rede","diagnostico"],"ativo":true}')
        self.txt_input.setFixedHeight(260)
        col_in.addWidget(self.txt_input)
        col_editors.addLayout(col_in)

        # Lado 2: Saída
        col_out = QVBoxLayout()
        row_out_bar = QHBoxLayout()
        row_out_bar.addWidget(QLabel("Resultado Formatado:"))
        row_out_bar.addStretch()

        btn_copy = QPushButton("Copiar")
        btn_copy.clicked.connect(self._copy_result)
        row_out_bar.addWidget(btn_copy)
        col_out.addLayout(row_out_bar)

        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setFixedHeight(260)
        col_out.addWidget(self.txt_output)
        col_editors.addLayout(col_out)

        layout.addLayout(col_editors)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._do_beautify()

    def _do_beautify(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            return
        lang = self.cmb_lang.currentText()
        indent = 4 if "4" in self.cmb_indent.currentText() else 2
        try:
            res = beautify_code(text, lang, indent)
            self.txt_output.setPlainText(res)
        except Exception as e:
            QMessageBox.critical(self, "Erro de Sintaxe", f"Não foi possível formatar {lang}:\n{str(e)}")

    def _do_minify(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            return
        lang = self.cmb_lang.currentText()
        try:
            res = minify_code(text, lang)
            self.txt_output.setPlainText(res)
        except Exception as e:
            QMessageBox.critical(self, "Erro de Sintaxe", f"Não foi possível minificar {lang}:\n{str(e)}")

    def _swap_texts(self):
        out = self.txt_output.toPlainText()
        self.txt_input.setPlainText(out)
        self.txt_output.clear()

    def _clear(self):
        self.txt_input.clear()
        self.txt_output.clear()

    def _copy_result(self):
        text = self.txt_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", "Código copiado para a área de transferência!")
