"""
Ferramenta: Codificador e Decodificador Universal.
Suporta Base64, URL Encode, HTML Entities, Hexadecimal, Unicode Escape e ROT13.
"""
import base64
import codecs
import html
import urllib.parse
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from .logic import SUPPORTED_ENCODINGS, decode_text, encode_text

@register
class EncodersTool(Tool):
    id = "encode.encoders"
    name = "Codificador e Decodificador Universal"
    category = "Codificação e Hash"
    description = "Codifica e decodifica textos em Base64, URL, HTML, Hexadecimal, Unicode e ROT13"
    keywords = ["base64", "urlencode", "html", "hex", "unicode", "rot13", "codificar", "decodificar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return EncodersView(self, parent)

class EncodersView(QWidget):
    def __init__(self, tool: EncodersTool, parent: Optional[QWidget] = None):
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

        # Seletor de Formato
        card_sel = QFrame()
        card_sel.setProperty("class", "card")
        l_sel = QHBoxLayout(card_sel)
        l_sel.addWidget(QLabel("Formato de Codificação:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(SUPPORTED_ENCODINGS)
        l_sel.addWidget(self.cmb_format, stretch=1)
        layout.addWidget(card_sel)

        # Entrada de Texto
        col_in = QVBoxLayout()
        col_in.addWidget(QLabel("Texto de Entrada:"))
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Digite ou cole o texto que deseja codificar ou decodificar...")
        self.txt_input.setFixedHeight(140)
        col_in.addWidget(self.txt_input)
        layout.addLayout(col_in)

        # Barra de Ações
        bar_act = QHBoxLayout()
        self.btn_encode = QPushButton("Codificar →")
        self.btn_encode.setProperty("class", "primary")
        self.btn_encode.setFixedHeight(34)
        self.btn_encode.clicked.connect(self._do_encode)
        bar_act.addWidget(self.btn_encode)

        self.btn_decode = QPushButton("← Decodificar")
        self.btn_decode.setFixedHeight(34)
        self.btn_decode.clicked.connect(self._do_decode)
        bar_act.addWidget(self.btn_decode)

        self.btn_swap = QPushButton("Inverter (Saída vira Entrada)")
        self.btn_swap.setFixedHeight(34)
        self.btn_swap.clicked.connect(self._swap_texts)
        bar_act.addWidget(self.btn_swap)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.setFixedHeight(34)
        self.btn_clear.clicked.connect(self._clear)
        bar_act.addWidget(self.btn_clear)
        bar_act.addStretch()

        self.btn_copy = QPushButton("Copiar Resultado")
        self.btn_copy.setFixedHeight(34)
        self.btn_copy.clicked.connect(self._copy_result)
        bar_act.addWidget(self.btn_copy)
        layout.addLayout(bar_act)

        # Saída de Texto
        col_out = QVBoxLayout()
        col_out.addWidget(QLabel("Resultado:"))
        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setFixedHeight(140)
        col_out.addWidget(self.txt_output)
        layout.addLayout(col_out)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _do_encode(self):
        text = self.txt_input.toPlainText()
        fmt = self.cmb_format.currentText()
        try:
            res = encode_text(text, fmt)
            self.txt_output.setPlainText(res)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao codificar texto:\n{str(e)}")

    def _do_decode(self):
        text = self.txt_input.toPlainText()
        fmt = self.cmb_format.currentText()
        try:
            res = decode_text(text, fmt)
            self.txt_output.setPlainText(res)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao decodificar texto:\n{str(e)}")

    def _swap_texts(self):
        out_txt = self.txt_output.toPlainText()
        self.txt_input.setPlainText(out_txt)
        self.txt_output.clear()

    def _clear(self):
        self.txt_input.clear()
        self.txt_output.clear()

    def _copy_result(self):
        res = self.txt_output.toPlainText()
        if res:
            QApplication.clipboard().setText(res)
            QMessageBox.information(self, "Copiado", "Resultado copiado para a área de transferência!")
