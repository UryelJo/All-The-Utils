"""
Página Inicial (Home Page).
Catálogo estruturado, moderno e filtrável de ferramentas disponíveis no All the Utils.
"""
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import BaseTool, FileTool, get_all_tools, get_categories

CATEGORY_ICONS = {
    "Imagens": "🖼️",
    "Arquivos e Pastas": "📁",
    "Rede e Internet": "🌐",
    "Documentos e PDF": "📄",
    "Texto e Redação": "📝",
    "Codificação e Hash": "🔐",
    "Dados e Estruturas": "📊",
    "Áudio e Vídeo": "🎬",
    "Sistema Windows": "🛠️",
    "Compactação": "📦",
}


class ToolCardWidget(QFrame):
    """Card individual e clicável para uma ferramenta."""
    clicked = Signal(str)

    def __init__(self, tool: BaseTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            ToolCardWidget {
                background-color: #27272b;
                border: 1px solid #393940;
                border-radius: 8px;
                padding: 10px 14px;
            }
            ToolCardWidget:hover {
                background-color: #323238;
                border-color: #0078d4;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        r_top = QHBoxLayout()
        lbl_name = QLabel(tool.name)
        lbl_name.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")
        r_top.addWidget(lbl_name)
        r_top.addStretch()

        badge_type = "Lote" if isinstance(tool, FileTool) else "Painel"
        badge_color = "#0e639c" if isinstance(tool, FileTool) else "#388a34"
        lbl_badge = QLabel(badge_type)
        lbl_badge.setStyleSheet(f"""
            background-color: {badge_color};
            color: #ffffff;
            font-size: 10px;
            font-weight: 600;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        r_top.addWidget(lbl_badge)
        layout.addLayout(r_top)

        lbl_desc = QLabel(tool.description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 12px; color: #a1a1aa;")
        layout.addWidget(lbl_desc)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.tool.id)
        super().mousePressEvent(event)


class HomePage(QWidget):
    """Visão inicial apresentando catálogo visual de todas as ferramentas."""
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
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(24)

        # Hero Banner
        hero = QFrame()
        hero.setObjectName("heroCard")
        hero.setStyleSheet("""
            QFrame#heroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2a3a, stop:1 #242428);
                border: 1px solid #2d4560;
                border-radius: 10px;
            }
        """)
        l_hero = QVBoxLayout(hero)
        l_hero.setContentsMargins(20, 18, 20, 18)
        l_hero.setSpacing(6)

        lbl_welcome = QLabel("All the Utils — Central de Produtividade")
        lbl_welcome.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        l_hero.addWidget(lbl_welcome)

        total_count = len(get_all_tools())
        lbl_desc = QLabel(f"São {total_count} ferramentas nativas para Windows com aceleração de hardware e processamento paralelo.")
        lbl_desc.setStyleSheet("font-size: 13px; color: #b4c7dc;")
        l_hero.addWidget(lbl_desc)

        layout.addWidget(hero)

        # Categorias e Ferramentas em Grade
        categories = get_categories()
        for cat_name, tools in categories.items():
            icon = CATEGORY_ICONS.get(cat_name, "📁")
            cat_group = QFrame()
            cat_group.setProperty("class", "card")
            cat_layout = QVBoxLayout(cat_group)
            cat_layout.setContentsMargins(18, 16, 18, 18)
            cat_layout.setSpacing(12)

            r_cat_hdr = QHBoxLayout()
            lbl_cat = QLabel(f"{icon}  {cat_name} ({len(tools)})")
            lbl_cat.setStyleSheet("font-weight: 700; font-size: 15px; color: #ffffff;")
            r_cat_hdr.addWidget(lbl_cat)
            r_cat_hdr.addStretch()
            cat_layout.addLayout(r_cat_hdr)

            # Grade de cards de 2 colunas
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(10)

            for idx, t in enumerate(tools):
                card = ToolCardWidget(t)
                card.clicked.connect(self.tool_requested.emit)
                row = idx // 2
                col = idx % 2
                grid.addWidget(card, row, col)

            cat_layout.addLayout(grid)
            layout.addWidget(cat_group)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)
