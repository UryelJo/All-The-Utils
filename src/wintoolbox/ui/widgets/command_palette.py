"""
Paleta de Comandos Rápida (Command Palette - Ctrl+K).
Modal de busca instantânea para encontrar e abrir qualquer ferramenta.
"""
from typing import Callable, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import BaseTool, get_all_tools

class CommandPaletteDialog(QDialog):
    """Diálogo modal acionado por Ctrl+K para busca e navegação rápida."""
    tool_selected = Signal(str)  # tool_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(540, 360)

        self._tools: List[BaseTool] = get_all_tools()
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame(self)
        container.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #0078d4;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(8)

        # Campo de entrada
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Digite o nome ou finalidade da ferramenta...")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
                color: #ffffff;
            }
        """)
        self.txt_search.textChanged.connect(self._filter_tools)
        c_layout.addWidget(self.txt_search)

        # Lista de resultados
        self.list_results = QListWidget()
        self.list_results.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 4px;
                color: #f1f1f1;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
        """)
        self.list_results.itemActivated.connect(self._on_item_activated)
        c_layout.addWidget(self.list_results)

        # Dica de atalhos
        lbl_hint = QLabel("Pressione Enter para abrir, Esc para fechar, ↑ ↓ para navegar")
        lbl_hint.setStyleSheet("color: #888888; font-size: 11px;")
        c_layout.addWidget(lbl_hint)

        root_layout.addWidget(container)
        self._populate_list(self._tools)

    def _populate_list(self, tools: List[BaseTool]):
        self.list_results.clear()
        for t in tools:
            item = QListWidgetItem(f"{t.name}  [{t.category}]")
            item.setData(Qt.UserRole, t.id)
            self.list_results.addItem(item)
        if self.list_results.count() > 0:
            self.list_results.setCurrentRow(0)

    def _filter_tools(self, query: str):
        query = query.strip().lower()
        if not query:
            self._populate_list(self._tools)
            return

        filtered = []
        for t in self._tools:
            match = False
            if query in t.name.lower() or query in t.description.lower() or query in t.category.lower():
                match = True
            elif any(query in kw.lower() for kw in t.keywords):
                match = True
            if match:
                filtered.append(t)

        self._populate_list(filtered)

    def _on_item_activated(self, item: QListWidgetItem):
        tool_id = item.data(Qt.UserRole)
        if tool_id:
            self.tool_selected.emit(tool_id)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            curr = self.list_results.currentItem()
            if curr:
                self._on_item_activated(curr)
        elif event.key() == Qt.Key_Down:
            row = self.list_results.currentRow()
            if row < self.list_results.count() - 1:
                self.list_results.setCurrentRow(row + 1)
        elif event.key() == Qt.Key_Up:
            row = self.list_results.currentRow()
            if row > 0:
                self.list_results.setCurrentRow(row - 1)
        else:
            super().keyPressEvent(event)
