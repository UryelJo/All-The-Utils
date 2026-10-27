"""
Paleta de Comandos Rápida (Command Palette - Ctrl+K) estilo Raycast / PowerToys Run.
Suporta busca fuzzy tolerante a acentos e erros de digitação via rapidfuzz,
priorizando Favoritos e Recentes no topo.
"""
from typing import List, Optional, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QVBoxLayout, QWidget
)
from rapidfuzz import fuzz

from wintoolbox.core.registry import BaseTool, get_all_tools
from wintoolbox.core.search import calculate_tool_relevance
from wintoolbox.core.settings import load_settings
from wintoolbox.ui.icons import get_category_icon, get_glyph, get_icon_font, make_fluent_icon, normalize_text
from wintoolbox.ui.theme import get_current_tokens


class CommandPaletteDialog(QDialog):
    """Diálogo modal acionado por Ctrl+K para busca e navegação rápida."""
    tool_selected = Signal(str)  # tool_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(580, 400)

        self._tools: List[BaseTool] = get_all_tools()
        self._build_ui()

    def _build_ui(self) -> None:
        t = get_current_tokens()
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame(self)
        container.setObjectName("commandPaletteContainer")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(14, 14, 14, 12)
        c_layout.setSpacing(10)

        # Barra de busca limpa
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Pesquisar ferramenta, categoria ou ação (ex: pdf, wifi, hash, dns)...")
        self.txt_search.textChanged.connect(self._filter_tools)
        search_row.addWidget(self.txt_search, stretch=1)
        c_layout.addLayout(search_row)

        # Lista de resultados
        self.list_results = QListWidget()
        self.list_results.itemActivated.connect(self._on_item_activated)
        self.list_results.itemClicked.connect(self._on_item_activated)
        c_layout.addWidget(self.list_results, stretch=1)

        # Rodapé de atalhos
        footer = QHBoxLayout()
        lbl_hint = QLabel("Enter para abrir  |  Setas para navegar  |  Esc para fechar")
        lbl_hint.setProperty("class", "muted")
        footer.addWidget(lbl_hint)
        footer.addStretch()

        lbl_count = QLabel(f"{len(self._tools)} ferramentas no catálogo")
        lbl_count.setProperty("class", "muted")
        self.lbl_count = lbl_count
        footer.addWidget(lbl_count)
        c_layout.addLayout(footer)

        root_layout.addWidget(container)
        self._populate_default_list()
        self.txt_search.setFocus()

    def _populate_default_list(self) -> None:
        """Exibe Favoritos e Recentes no topo seguidos do catálogo completo."""
        st = load_settings()
        fav_ids = set(st.get("favorites", []))
        recent_ids = st.get("recent_tools", [])

        ordered: List[Tuple[BaseTool, str]] = []
        seen = set()

        for tid in fav_ids:
            for tool in self._tools:
                if tool.id == tid and tool.id not in seen:
                    ordered.append((tool, "Favorito"))
                    seen.add(tool.id)

        for tid in recent_ids[:5]:
            for tool in self._tools:
                if tool.id == tid and tool.id not in seen:
                    ordered.append((tool, "Recente"))
                    seen.add(tool.id)

        for tool in self._tools:
            if tool.id not in seen:
                ordered.append((tool, ""))
                seen.add(tool.id)

        self._render_items(ordered)

    def _render_items(self, items: List[Tuple[BaseTool, str]]) -> None:
        self.list_results.clear()
        for t, tag in items:
            tag_prefix = f"[{tag}]  " if tag else ""
            label = f"{tag_prefix}{t.name}   —   {t.category}\n{t.description}"
            item = QListWidgetItem(get_category_icon(t.category, size=18), label)
            item.setData(Qt.UserRole, t.id)
            self.list_results.addItem(item)

        self.lbl_count.setText(f"{len(items)} resultado(s)")
        if self.list_results.count() > 0:
            self.list_results.setCurrentRow(0)

    def _filter_tools(self, query: str) -> None:
        q = query.strip()
        if not q:
            self._populate_default_list()
            return

        scored: List[Tuple[int, BaseTool]] = []
        for t in self._tools:
            score = calculate_tool_relevance(t, q)
            if score > 0:
                scored.append((score, t))

        # Prioridade máxima para matches no Nome, seguidos de matches na Descrição
        scored.sort(key=lambda x: (-x[0], normalize_text(x[1].name)))
        self._render_items([(tool, "") for _, tool in scored])

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        tool_id = item.data(Qt.UserRole)
        if tool_id:
            self.tool_selected.emit(tool_id)
            self.accept()

    def keyPressEvent(self, event) -> None:
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
