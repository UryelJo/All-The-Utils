"""
Interface gráfica da ferramenta Conversor Bidirecional XML e JSON (data.xml_json).
Permite converter XML para JSON e JSON para XML em tempo real, preservando atributos (@) e elementos repetidos.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.xml_json.logic import (
    json_to_xml,
    xml_to_json,
)


@register
class XmlJsonTool(Tool):
    id = "data.xml_json"
    name = "Conversor XML e JSON"
    category = "Dados e Estruturas"
    description = (
        "Conversão bidirecional entre XML e JSON preservando atributos (@), "
        "hierarquias aninhadas, listas de elementos e texto semântico."
    )
    keywords = ["xml", "json", "converter", "bidirecional", "arvore", "dados", "atributos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return XmlJsonView(self, parent)


class XmlJsonView(QWidget):
    def __init__(self, tool: XmlJsonTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Barra de Opções Superior
        opts_bar = QHBoxLayout()
        self._chk_declaration = QCheckBox("Incluir declaração <?xml ...?> no XML gerado")
        self._chk_declaration.setChecked(True)
        opts_bar.addWidget(self._chk_declaration)

        opts_bar.addStretch()

        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setStyleSheet("color: #4b5563; font-size: 11px;")
        opts_bar.addWidget(self._lbl_status)

        root_layout.addLayout(opts_bar)

        # Splitter Horizontal: XML à esquerda, Painel de Conversão central, JSON à direita
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel XML (Esquerda)
        xml_group = QGroupBox("Documento XML")
        xml_layout = QVBoxLayout(xml_group)
        self._txt_xml = QPlainTextEdit()
        self._txt_xml.setFont(QFont("Consolas", 9))
        self._txt_xml.setPlaceholderText("<loja>\n  <produto id=\"1\">\n    <nome>Notebook</nome>\n  </produto>\n</loja>")
        xml_layout.addWidget(self._txt_xml)

        xml_act = QHBoxLayout()
        btn_copy_xml = QPushButton("Copiar XML")
        btn_copy_xml.clicked.connect(self._copy_xml)
        xml_act.addWidget(btn_copy_xml)

        btn_sample_xml = QPushButton("Carregar Exemplo XML")
        btn_sample_xml.clicked.connect(self._load_sample)
        xml_act.addWidget(btn_sample_xml)
        xml_act.addStretch()
        xml_layout.addLayout(xml_act)

        splitter.addWidget(xml_group)

        # Painel Central com Botões de Conversão
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 4, 4, 4)
        center_layout.setSpacing(12)
        center_layout.addStretch()

        btn_xml_to_json = QPushButton("XML  ➔  JSON")
        btn_xml_to_json.setStyleSheet("font-weight: bold; padding: 10px 14px;")
        btn_xml_to_json.clicked.connect(self._convert_xml_to_json)
        center_layout.addWidget(btn_xml_to_json)

        btn_json_to_xml = QPushButton("JSON  ➔  XML")
        btn_json_to_xml.setStyleSheet("font-weight: bold; padding: 10px 14px;")
        btn_json_to_xml.clicked.connect(self._convert_json_to_xml)
        center_layout.addWidget(btn_json_to_xml)

        center_layout.addStretch()
        splitter.addWidget(center_widget)

        # Painel JSON (Direita)
        json_group = QGroupBox("Documento JSON")
        json_layout = QVBoxLayout(json_group)
        self._txt_json = QPlainTextEdit()
        self._txt_json.setFont(QFont("Consolas", 9))
        self._txt_json.setPlaceholderText('{\n  "loja": {\n    "produto": {\n      "@id": "1",\n      "nome": "Notebook"\n    }\n  }\n}')
        json_layout.addWidget(self._txt_json)

        json_act = QHBoxLayout()
        btn_copy_json = QPushButton("Copiar JSON")
        btn_copy_json.clicked.connect(self._copy_json)
        json_act.addWidget(btn_copy_json)
        json_act.addStretch()
        json_layout.addLayout(json_act)

        splitter.addWidget(json_group)

        splitter.setSizes([380, 140, 380])
        root_layout.addWidget(splitter)

    def _convert_xml_to_json(self):
        raw_xml = self._txt_xml.toPlainText().strip()
        if not raw_xml:
            QMessageBox.warning(self, "Aviso", "Por favor, insira o XML de entrada.")
            return

        try:
            res_json = xml_to_json(raw_xml)
            self._txt_json.setPlainText(res_json)
            self._lbl_status.setText("Convertido de XML para JSON com sucesso!")
        except Exception as exc:
            QMessageBox.critical(self, "Erro na Conversão", f"Falha ao processar XML: {exc}")
            self._lbl_status.setText("Erro na conversão do XML.")

    def _convert_json_to_xml(self):
        raw_json = self._txt_json.toPlainText().strip()
        if not raw_json:
            QMessageBox.warning(self, "Aviso", "Por favor, insira o JSON de entrada.")
            return

        inc_dec = self._chk_declaration.isChecked()
        try:
            res_xml = json_to_xml(raw_json, include_declaration=inc_dec)
            self._txt_xml.setPlainText(res_xml)
            self._lbl_status.setText("Convertido de JSON para XML com sucesso!")
        except Exception as exc:
            QMessageBox.critical(self, "Erro na Conversão", f"Falha ao processar JSON: {exc}")
            self._lbl_status.setText("Erro na conversão do JSON.")

    def _load_sample(self):
        sample = (
            '<catalogo versao="2.0">\n'
            '  <servidor regiao="sa-east-1">\n'
            '    <host>cluster-prod-01</host>\n'
            '    <ativo>true</ativo>\n'
            '    <capacidade>16GB</capacidade>\n'
            '  </servidor>\n'
            '</catalogo>'
        )
        self._txt_xml.setPlainText(sample)
        self._convert_xml_to_json()

    def _copy_xml(self):
        txt = self._txt_xml.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)

    def _copy_json(self):
        txt = self._txt_json.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
