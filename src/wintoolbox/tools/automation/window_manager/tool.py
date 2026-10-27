"""
Interface gráfica do Gerenciador de Janelas do Windows.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.window_manager.logic import (
    list_open_windows, set_window_always_on_top, set_window_transparency,
    snap_window
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("automation.window_manager.ui")


@register
class WindowManagerTool(Tool):
    id = "automation.window_manager"
    name = "Gerenciador de Janelas"
    category = "Automação"
    description = "Gerenciador de janelas do Windows: fixa janelas sempre visíveis no topo (Always on Top), ajusta nível de transparência (Opacidade) e organiza layouts de snap."
    keywords = ["janelas", "always on top", "topo", "transparencia", "snap", "posicionar", "windows", "automacao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return WindowManagerView(self, parent)


class WindowManagerView(QWidget):
    def __init__(self, tool: WindowManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._windows: List[Dict[str, Any]] = []
        self._selected_hwnd: Optional[int] = None

        self._build_ui()
        self._refresh_windows()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Gerenciador de Janelas do Windows",
            "Mantenha qualquer programa sempre visível por cima de outros, aplique transparência e organize o layout da tela."
        ))

        # Barra de Filtro e Atualização
        bar = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Filtrar janelas abertas por nome...")
        self.edit_search.textChanged.connect(self._filter_list)
        bar.addWidget(self.edit_search, stretch=1)

        btn_refresh = QPushButton("Atualizar Janelas")
        btn_refresh.clicked.connect(self._refresh_windows)
        bar.addWidget(btn_refresh)
        root.addLayout(bar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # Coluna Esquerda: Lista de Janelas
        left_box = QGroupBox("Janelas Abertas no Sistema")
        left_layout = QVBoxLayout(left_box)
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_window_selected)
        left_layout.addWidget(self.list_widget)
        content_layout.addWidget(left_box, stretch=2)

        # Coluna Direita: Controles da Janela Selecionada
        right_box = QGroupBox("Controles da Janela Selecionada")
        right_layout = QVBoxLayout(right_box)
        right_layout.setSpacing(12)

        self.lbl_selected_title = QLabel("Nenhuma janela selecionada.")
        self.lbl_selected_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_selected_title.setWordWrap(True)
        right_layout.addWidget(self.lbl_selected_title)

        # 1. Sempre no Topo
        self.btn_topmost = QPushButton("Fixar 'Sempre no Topo'")
        self.btn_topmost.setEnabled(False)
        self.btn_topmost.clicked.connect(self._toggle_topmost)
        right_layout.addWidget(self.btn_topmost)

        # 2. Transparência / Opacidade
        trans_box = QGroupBox("Transparência / Opacidade")
        trans_layout = QVBoxLayout(trans_box)
        trans_layout.setSpacing(6)

        self.lbl_opacity = QLabel("Opacidade: 100% (Sólido)")
        trans_layout.addWidget(self.lbl_opacity)

        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setEnabled(False)
        self.slider_opacity.valueChanged.connect(self._on_opacity_changed)
        trans_layout.addWidget(self.slider_opacity)

        btn_reset_trans = QPushButton("Restaurar Opacidade 100%")
        btn_reset_trans.clicked.connect(lambda: self.slider_opacity.setValue(100))
        trans_layout.addWidget(btn_reset_trans)

        right_layout.addWidget(trans_box)

        # 3. Alinhamento Rápido (Snap)
        snap_box = QGroupBox("Alinhamento e Posicionamento (Snap)")
        snap_grid = QGridLayout(snap_box)
        snap_grid.setSpacing(6)

        btn_left = QPushButton("Metade Esquerda")
        btn_left.clicked.connect(lambda: self._snap("left"))
        snap_grid.addWidget(btn_left, 0, 0)

        btn_right = QPushButton("Metade Direita")
        btn_right.clicked.connect(lambda: self._snap("right"))
        snap_grid.addWidget(btn_right, 0, 1)

        btn_top = QPushButton("Metade Superior")
        btn_top.clicked.connect(lambda: self._snap("top"))
        snap_grid.addWidget(btn_top, 1, 0)

        btn_bottom = QPushButton("Metade Inferior")
        btn_bottom.clicked.connect(lambda: self._snap("bottom"))
        snap_grid.addWidget(btn_bottom, 1, 1)

        btn_center = QPushButton("Centralizar Tela")
        btn_center.clicked.connect(lambda: self._snap("center"))
        snap_grid.addWidget(btn_center, 2, 0)

        btn_max = QPushButton("Maximizar na Área Útil")
        btn_max.clicked.connect(lambda: self._snap("maximize"))
        snap_grid.addWidget(btn_max, 2, 1)

        right_layout.addWidget(snap_box)
        right_layout.addStretch(1)

        content_layout.addWidget(right_box, stretch=1)
        root.addLayout(content_layout, stretch=1)

    def _refresh_windows(self) -> None:
        self._windows = list_open_windows()
        self._filter_list()

    def _filter_list(self) -> None:
        search = self.edit_search.text().lower().strip()
        self.list_widget.clear()

        for win in self._windows:
            title = win["title"]
            if search and search not in title.lower():
                continue

            top_badge = " [Sempre no Topo]" if win["is_topmost"] else ""
            item = QListWidgetItem(f"{title}{top_badge}")
            item.setData(Qt.ItemDataRole.UserRole, win["hwnd"])
            self.list_widget.addItem(item)

    def _on_window_selected(self, row: int) -> None:
        item = self.list_widget.currentItem()
        if not item:
            self._selected_hwnd = None
            self.lbl_selected_title.setText("Nenhuma janela selecionada.")
            self.btn_topmost.setEnabled(False)
            self.slider_opacity.setEnabled(False)
            return

        hwnd = item.data(Qt.ItemDataRole.UserRole)
        self._selected_hwnd = hwnd
        title = item.text()
        self.lbl_selected_title.setText(f"Janela: {title}")
        self.btn_topmost.setEnabled(True)
        self.slider_opacity.setEnabled(True)

        is_top = "[Sempre no Topo]" in title
        self.btn_topmost.setText("Desafixar do Topo" if is_top else "Fixar 'Sempre no Topo'")

    def _toggle_topmost(self) -> None:
        if not self._selected_hwnd:
            return

        current_text = self.btn_topmost.text()
        enable = "Fixar" in current_text

        ok = set_window_always_on_top(self._selected_hwnd, enable)
        if ok:
            show_toast(self, "Janela fixada no topo!" if enable else "Janela desafixada do topo.")
            self._refresh_windows()
        else:
            show_toast(self, "Não foi possível alterar a propriedade da janela.")

    def _on_opacity_changed(self, value: int) -> None:
        self.lbl_opacity.setText(f"Opacidade: {value}%")
        if self._selected_hwnd:
            set_window_transparency(self._selected_hwnd, value)

    def _snap(self, position: str) -> None:
        if not self._selected_hwnd:
            show_toast(self, "Selecione uma janela na lista primeiro.")
            return
        ok = snap_window(self._selected_hwnd, position)
        if ok:
            show_toast(self, f"Janela reposicionada ({position})!")
        else:
            show_toast(self, "Falha ao mover janela.")
