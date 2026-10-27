"""
Interface gráfica da ferramenta Codificador e Catálogo de Entidades HTML (encode.html_entities).
Permite conversão em entidades nomeadas, decimais, hexadecimais, decodificação completa
e consulta rápida com tabela pesquisável de entidades padrão.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.html_entities.logic import (
    COMMON_ENTITIES,
    decode_html,
    encode_html,
    filter_catalog,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class HtmlEntitiesTool(Tool):
    id = "encode.html_entities"
    name = "Entidades HTML e Caracteres Especiais"
    category = "Codificação e Hash"
    description = (
        "Codifica e decodifica entidades HTML (nomeadas, decimais e hexadecimais) "
        "com catálogo interativo de símbolos e caracteres especiais."
    )
    keywords = ["html", "entidades", "escape", "unescape", "unicode", "caracteres", "amp", "lt", "gt"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HtmlEntitiesView(self, parent)


class HtmlEntitiesView(QWidget):
    def __init__(self, tool: HtmlEntitiesTool, parent: Optional[QWidget] = None):
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

        # Abas
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_converter_tab(), "Conversor Bidirecional")
        self._tabs.addTab(self._build_catalog_tab(), "Catálogo de Entidades")
        root_layout.addWidget(self._tabs)

    def _build_converter_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Barra de Controles
        ctrl_bar = QHBoxLayout()
        ctrl_bar.addWidget(QLabel("Formato de Codificação:"))
        self._combo_mode = QComboBox()
        self._combo_mode.addItem("Entidades Nomeadas (&copy;)", "named")
        self._combo_mode.addItem("Numérico Decimal (&#169;)", "decimal")
        self._combo_mode.addItem("Numérico Hexadecimal (&#xA9;)", "hex")
        ctrl_bar.addWidget(self._combo_mode)

        self._chk_only_reserved = QCheckBox("Apenas reservados HTML (<, >, &, \", ')")
        ctrl_bar.addWidget(self._chk_only_reserved)

        ctrl_bar.addStretch()
        layout.addLayout(ctrl_bar)

        # Splitter Vertical: Entrada em cima, Saída embaixo
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Painel de Entrada
        in_group = QGroupBox("Texto de Entrada")
        in_layout = QVBoxLayout(in_group)
        self._txt_in = QPlainTextEdit()
        self._txt_in.setFont(QFont("Consolas", 10))
        self._txt_in.setPlaceholderText("Digite ou cole o texto ou entidades HTML aqui...")
        in_layout.addWidget(self._txt_in)
        splitter.addWidget(in_group)

        # Painel de Saída
        out_group = QGroupBox("Resultado")
        out_layout = QVBoxLayout(out_group)
        self._txt_out = QPlainTextEdit()
        self._txt_out.setFont(QFont("Consolas", 10))
        self._txt_out.setReadOnly(True)
        out_layout.addWidget(self._txt_out)
        splitter.addWidget(out_group)

        splitter.setSizes([220, 220])
        layout.addWidget(splitter)

        # Botões de Ação
        act_bar = QHBoxLayout()
        btn_encode = QPushButton("Codificar para HTML")
        btn_encode.clicked.connect(self._on_encode)
        act_bar.addWidget(btn_encode)

        btn_decode = QPushButton("Decodificar de HTML")
        btn_decode.clicked.connect(self._on_decode)
        act_bar.addWidget(btn_decode)

        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.clicked.connect(self._copy_output)
        act_bar.addWidget(btn_copy)

        act_bar.addStretch()
        layout.addLayout(act_bar)

        return widget

    def _build_catalog_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Barra de Busca
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Filtrar Entidades:"))
        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Buscar por caractere, nome (&copy;) ou descrição...")
        self._txt_search.textChanged.connect(self._on_search_catalog)
        search_bar.addWidget(self._txt_search)
        layout.addLayout(search_bar)

        # Tabela com DataTableView
        cols = [
            Column("char", "Caractere", width=90),
            Column("name", "Nomeada", width=120),
            Column("dec", "Decimal", width=100),
            Column("hex", "Hexadecimal", width=110),
            Column("desc", "Descrição", width=340),
        ]
        self._catalog_table = DataTableView(cols, key="name", parent=self)
        self._catalog_table.set_records(COMMON_ENTITIES)
        layout.addWidget(self._catalog_table)

        return widget

    def _on_encode(self):
        raw = self._txt_in.toPlainText()
        mode = self._combo_mode.currentData()
        only_res = self._chk_only_reserved.isChecked()
        encoded = encode_html(raw, mode=mode, only_reserved=only_res)
        self._txt_out.setPlainText(encoded)

    def _on_decode(self):
        raw = self._txt_in.toPlainText()
        decoded = decode_html(raw)
        self._txt_out.setPlainText(decoded)

    def _copy_output(self):
        txt = self._txt_out.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)

    def _on_search_catalog(self, query: str):
        filtered = filter_catalog(query)
        self._catalog_table.set_records(filtered)
