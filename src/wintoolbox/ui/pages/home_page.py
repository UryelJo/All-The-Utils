"""
Página Inicial (Home Page).
Catálogo estruturado e filtrável de ferramentas disponíveis no WinToolbox.
"""
from typing import Callable, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import BaseTool, get_categories

class HomePage(QWidget):
    """Visão de início apresentando todas as ferramentas agrupadas por categoria."""
    tool_requested = Signal(str)  # tool_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Cabeçalho Principal
        lbl_welcome = QLabel("Caixa de Ferramentas")
        lbl_welcome.setProperty("class", "title")
        layout.addWidget(lbl_welcome)

        lbl_desc = QLabel("Selecione uma ferramenta abaixo ou use o atalho Ctrl+K para busca rápida.")
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Categorias e Ferramentas
        categories = get_categories()
        for cat_name, tools in categories.items():
            cat_group = QFrame()
            cat_group.setProperty("class", "card")
            cat_layout = QVBoxLayout(cat_group)
            cat_layout.setContentsMargins(14, 12, 14, 12)
            cat_layout.setSpacing(8)

            lbl_cat = QLabel(cat_name)
            lbl_cat.setStyleSheet("font-weight: 600; font-size: 14px;")
            cat_layout.addWidget(lbl_cat)

            for t in tools:
                btn_tool = QPushButton(f"{t.name} — {t.description}")
                btn_tool.setStyleSheet("""
                    QPushButton {
                        text-align: left;
                        padding: 8px 12px;
                        background: transparent;
                        border: none;
                        border-bottom: 1px solid #333333;
                        border-radius: 0px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #2e2e32;
                    }
                """)
                btn_tool.clicked.connect(lambda checked=False, tid=t.id: self.tool_requested.emit(tid))
                cat_layout.addWidget(btn_tool)

            layout.addWidget(cat_group)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)
