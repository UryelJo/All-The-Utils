"""
Interface de usuário para a ferramenta Tabelas de Referência Técnica.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.reference.logic import (
    HTTP_STATUS_LIST,
    MIME_TYPES_LIST,
    SHORTCUTS_LIST,
    VIRTUAL_KEYS_LIST,
    get_ascii_table,
    search_reference,
)


@register
class TechnicalReferenceTool(Tool):
    """Guia rápido de referência técnica offline para desenvolvedores."""

    id = "dev.reference"
    name = "Tabelas de Referência Técnica"
    description = "Guia de consulta offline de status HTTP, tipos MIME, tabela ASCII/Hex, teclas virtuais VK e atalhos do Windows."
    category = "dev"

    def __init__(self):
        super().__init__()
        self.ascii_list = get_ascii_table()

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Tabelas de Referência Técnica")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Consulte padrões de protocolo, codificações de caracteres, mapeamento de teclas "
            "e atalhos de produtividade com filtragem instantânea offline."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Campo de Busca
        search_frame = QFrame()
        search_frame.setFrameShape(QFrame.Shape.StyledPanel)
        s_layout = QHBoxLayout(search_frame)
        s_layout.setContentsMargins(10, 8, 10, 8)

        s_layout.addWidget(QLabel("Filtrar Tabela Ativa:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Digite para buscar (ex: 404, json, Enter, Win+V)...")
        self.txt_filter.textChanged.connect(self._apply_filter)
        s_layout.addWidget(self.txt_filter, 1)

        self.btn_clear_filter = QPushButton("Limpar")
        self.btn_clear_filter.clicked.connect(self.txt_filter.clear)
        s_layout.addWidget(self.btn_clear_filter)

        layout.addWidget(search_frame)

        # Barra Inferior
        bottom_layout = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #888888;")

        self.btn_copy = QPushButton("Copiar Linha Selecionada")
        self.btn_copy.clicked.connect(self._copy_selected_row)

        bottom_layout.addWidget(self.lbl_count)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_copy)

        # Abas de Tabelas
        self.tabs = QTabWidget()

        # 1. HTTP
        self.table_http = QTableWidget()
        self.table_http.setColumnCount(4)
        self.table_http.setHorizontalHeaderLabels(["Código", "Nome", "Categoria", "Descrição"])
        self.table_http.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_http, "Status HTTP")

        # 2. MIME
        self.table_mime = QTableWidget()
        self.table_mime.setColumnCount(4)
        self.table_mime.setHorizontalHeaderLabels(["Extensão", "MIME Type", "Categoria", "Descrição"])
        self.table_mime.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_mime, "Tipos MIME")

        # 3. ASCII
        self.table_ascii = QTableWidget()
        self.table_ascii.setColumnCount(5)
        self.table_ascii.setHorizontalHeaderLabels(["Decimal", "Hex", "Binário", "Caractere", "Descrição"])
        self.table_ascii.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_ascii, "Tabela ASCII")

        # 4. Virtual Keys
        self.table_vk = QTableWidget()
        self.table_vk.setColumnCount(4)
        self.table_vk.setHorizontalHeaderLabels(["Nome Constante", "Código Hex", "Código Dec", "Descrição"])
        self.table_vk.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_vk, "Teclas Virtuais (VK)")

        # 5. Atalhos Windows
        self.table_shortcuts = QTableWidget()
        self.table_shortcuts.setColumnCount(3)
        self.table_shortcuts.setHorizontalHeaderLabels(["Atalho", "Categoria", "Descrição"])
        self.table_shortcuts.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_shortcuts, "Atalhos do Windows")

        layout.addWidget(self.tabs, 1)
        layout.addLayout(bottom_layout)

        self._populate_all()
        self.tabs.currentChanged.connect(self._apply_filter)
        return widget

    def _populate_all(self):
        self._load_http(HTTP_STATUS_LIST)
        self._load_mime(MIME_TYPES_LIST)
        self._load_ascii(self.ascii_list)
        self._load_vk(VIRTUAL_KEYS_LIST)
        self._load_shortcuts(SHORTCUTS_LIST)

    def _load_http(self, items):
        self.table_http.setRowCount(len(items))
        for r, i in enumerate(items):
            self.table_http.setItem(r, 0, QTableWidgetItem(str(i.code)))
            self.table_http.setItem(r, 1, QTableWidgetItem(i.phrase))
            self.table_http.setItem(r, 2, QTableWidgetItem(i.category))
            self.table_http.setItem(r, 3, QTableWidgetItem(i.description))

    def _load_mime(self, items):
        self.table_mime.setRowCount(len(items))
        for r, i in enumerate(items):
            self.table_mime.setItem(r, 0, QTableWidgetItem(i.extension))
            self.table_mime.setItem(r, 1, QTableWidgetItem(i.mime_type))
            self.table_mime.setItem(r, 2, QTableWidgetItem(i.category))
            self.table_mime.setItem(r, 3, QTableWidgetItem(i.description))

    def _load_ascii(self, items):
        self.table_ascii.setRowCount(len(items))
        for r, i in enumerate(items):
            self.table_ascii.setItem(r, 0, QTableWidgetItem(str(i.decimal)))
            self.table_ascii.setItem(r, 1, QTableWidgetItem(i.hexadecimal))
            self.table_ascii.setItem(r, 2, QTableWidgetItem(i.binary))
            self.table_ascii.setItem(r, 3, QTableWidgetItem(i.character))
            self.table_ascii.setItem(r, 4, QTableWidgetItem(i.description))

    def _load_vk(self, items):
        self.table_vk.setRowCount(len(items))
        for r, i in enumerate(items):
            self.table_vk.setItem(r, 0, QTableWidgetItem(i.vk_name))
            self.table_vk.setItem(r, 1, QTableWidgetItem(i.hex_code))
            self.table_vk.setItem(r, 2, QTableWidgetItem(str(i.dec_code)))
            self.table_vk.setItem(r, 3, QTableWidgetItem(i.description))

    def _load_shortcuts(self, items):
        self.table_shortcuts.setRowCount(len(items))
        for r, i in enumerate(items):
            self.table_shortcuts.setItem(r, 0, QTableWidgetItem(i.keys))
            self.table_shortcuts.setItem(r, 1, QTableWidgetItem(i.scope))
            self.table_shortcuts.setItem(r, 2, QTableWidgetItem(i.description))

    def _apply_filter(self):
        if not hasattr(self, "lbl_count"):
            return
        query = self.txt_filter.text().strip()
        idx = self.tabs.currentIndex()

        if idx == 0:
            filtered = search_reference(query, HTTP_STATUS_LIST)
            self._load_http(filtered)
            self.lbl_count.setText(f"{len(filtered)} códigos exibidos.")
        elif idx == 1:
            filtered = search_reference(query, MIME_TYPES_LIST)
            self._load_mime(filtered)
            self.lbl_count.setText(f"{len(filtered)} tipos MIME exibidos.")
        elif idx == 2:
            filtered = search_reference(query, self.ascii_list)
            self._load_ascii(filtered)
            self.lbl_count.setText(f"{len(filtered)} caracteres exibidos.")
        elif idx == 3:
            filtered = search_reference(query, VIRTUAL_KEYS_LIST)
            self._load_vk(filtered)
            self.lbl_count.setText(f"{len(filtered)} teclas virtuais exibidas.")
        elif idx == 4:
            filtered = search_reference(query, SHORTCUTS_LIST)
            self._load_shortcuts(filtered)
            self.lbl_count.setText(f"{len(filtered)} atalhos exibidos.")

    def _copy_selected_row(self):
        current_table: QTableWidget = self.tabs.currentWidget()
        row = current_table.currentRow()
        if row < 0:
            QMessageBox.information(None, "Aviso", "Selecione uma linha para copiar.")
            return

        values = []
        for col in range(current_table.columnCount()):
            item = current_table.item(row, col)
            values.append(item.text() if item else "")

        line_text = " | ".join(values)
        QGuiApplication.clipboard().setText(line_text)
        QMessageBox.information(None, "Copiado", f"Linha copiada:\n{line_text}")
