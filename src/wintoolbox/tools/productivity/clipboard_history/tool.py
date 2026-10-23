"""
Interface gráfica da ferramenta Histórico da Área de Transferência.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.clipboard_history.logic import (
    add_clipboard_item, clear_clipboard_history, delete_clipboard_item,
    list_clipboard_items, toggle_clipboard_favorite
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("productivity.clipboard_history.ui")


@register
class ClipboardHistoryTool(Tool):
    id = "productivity.clipboard_history"
    name = "Histórico da Área de Transferência"
    category = "Produtividade"
    description = "Registro contínuo, busca instantânea e favoritos de textos copiados no Windows"
    keywords = ["clipboard", "area de transferencia", "copiar", "colar", "historico", "favoritos", "texto"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ClipboardHistoryView(self, parent)


class ClipboardHistoryView(QWidget):
    def __init__(self, tool: ClipboardHistoryTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._self_copying = False
        self._items: List[Dict[str, Any]] = []

        self._build_ui()
        self._connect_clipboard_monitor()
        self._refresh_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Histórico da Área de Transferência",
            "Armazenamento local, busca e recuperação rápida de textos e códigos copiados no sistema."
        ))

        # Barra de ferramentas e controles
        bar_layout = QHBoxLayout()
        bar_layout.setSpacing(10)

        # Switch de monitoramento
        self.switch_monitor = ToggleSwitch()
        self.switch_monitor.setChecked(True)
        lbl_switch = QLabel("Monitoramento Ativo")
        bar_layout.addWidget(self.switch_monitor)
        bar_layout.addWidget(lbl_switch)
        bar_layout.addSpacing(16)

        # Campo de busca
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Pesquisar no histórico de textos...")
        self.edit_search.textChanged.connect(self._refresh_list)
        bar_layout.addWidget(self.edit_search, stretch=1)

        # Checkbox favoritos
        self.chk_favorites = QCheckBox("Apenas Favoritos")
        self.chk_favorites.toggled.connect(self._refresh_list)
        bar_layout.addWidget(self.chk_favorites)

        # Botão limpar
        btn_clear = QPushButton("Limpar Histórico")
        btn_clear.clicked.connect(self._on_clear_history)
        bar_layout.addWidget(btn_clear)

        root.addLayout(bar_layout)

        # Lista de Itens
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(6)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self.list_widget, stretch=1)

        # Rodapé com contador
        self.lbl_count = QLabel("Nenhum item registrado.")
        self.lbl_count.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        root.addWidget(self.lbl_count)

    def _connect_clipboard_monitor(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self) -> None:
        if not self.switch_monitor.isChecked() or self._self_copying:
            return

        text = QApplication.clipboard().text()
        if text and text.strip():
            add_clipboard_item(text)
            self._refresh_list()

    def _refresh_list(self) -> None:
        query = self.edit_search.text().strip()
        fav_only = self.chk_favorites.isChecked()
        self._items = list_clipboard_items(query=query, favorites_only=fav_only)

        self.list_widget.clear()

        for item_data in self._items:
            item = QListWidgetItem()
            widget = self._create_item_widget(item_data)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        total = len(self._items)
        fav_text = " (filtrado por favoritos)" if fav_only else ""
        self.lbl_count.setText(f"{total} item(ns) exibido(s){fav_text}. Dê duplo clique para copiar.")

    def _create_item_widget(self, data: Dict[str, Any]) -> QWidget:
        container = QFrame()
        container.setProperty("class", "card")
        container.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 6px; }")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Informações de texto
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        # Texto truncado para prévia
        content = data["content"]
        preview = content if len(content) <= 200 else content[:197] + "..."
        lbl_preview = QLabel(preview.replace("\n", " ").strip())
        lbl_preview.setFont(QFont("Cascadia Mono", 9))
        lbl_preview.setWordWrap(True)
        text_layout.addWidget(lbl_preview)

        # Metadados
        try:
            dt = datetime.fromisoformat(data["updated_at"]).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            dt = data["updated_at"]
        lbl_meta = QLabel(f"{dt} — {data['char_count']} caracteres")
        lbl_meta.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px;")
        text_layout.addWidget(lbl_meta)

        layout.addLayout(text_layout, stretch=1)

        # Ações do item
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        # Botão Copiar
        btn_copy = QPushButton("Copiar")
        btn_copy.setFixedWidth(65)
        btn_copy.clicked.connect(lambda checked=False, txt=content: self._copy_content(txt))
        actions_layout.addWidget(btn_copy)

        # Botão Favoritar
        is_fav = data["is_favorite"]
        btn_fav = QPushButton("Desfavoritar" if is_fav else "Favoritar")
        btn_fav.setFixedWidth(85)
        btn_fav.clicked.connect(lambda checked=False, i_id=data["id"]: self._toggle_favorite(i_id))
        actions_layout.addWidget(btn_fav)

        # Botão Excluir
        btn_del = QPushButton("Excluir")
        btn_del.setFixedWidth(65)
        btn_del.clicked.connect(lambda checked=False, i_id=data["id"]: self._delete_item(i_id))
        actions_layout.addWidget(btn_del)

        layout.addLayout(actions_layout)
        return container

    def _copy_content(self, text: str) -> None:
        self._self_copying = True
        try:
            QApplication.clipboard().setText(text)
            show_toast(self, "Texto copiado para a área de transferência!", duration_ms=1800)
        finally:
            QTimer.singleShot(400, lambda: setattr(self, "_self_copying", False))

    def _toggle_favorite(self, item_id: int) -> None:
        toggle_clipboard_favorite(item_id)
        self._refresh_list()

    def _delete_item(self, item_id: int) -> None:
        delete_clipboard_item(item_id)
        self._refresh_list()

    def _on_clear_history(self) -> None:
        count = clear_clipboard_history(keep_favorites=True)
        show_toast(self, f"{count} item(ns) removido(s). Favoritos preservados.")
        self._refresh_list()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        row = self.list_widget.row(item)
        if 0 <= row < len(self._items):
            self._copy_content(self._items[row]["content"])
