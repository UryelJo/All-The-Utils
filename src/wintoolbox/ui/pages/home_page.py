"""
Página Inicial Personalizável (Home Page / Hub de Produtividade Bento Grid).
Apresenta layout moderno em Bento Grid com cantos arredondados generosos,
Hero Accent Card, Smart Dropzone Bento Card, Telemetria de Hardware com medidores
gráficos elegantes, Acesso Rápido (Favoritos e Recentes), Filtro por Chips de
Categoria em formato pill e Catálogo Responsivo com micro-cartões interativos ↗.
"""
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import BaseTool, FileTool, get_all_tools, get_categories, get_tool
from wintoolbox.core.search import calculate_tool_relevance, search_and_rank_tools
from wintoolbox.core.settings import (
    get_home_layout, is_favorite, load_settings, toggle_favorite, update_home_layout
)
from wintoolbox.tools.system.monitor.logic import collect_hardware_metrics
from wintoolbox.ui.icons import (
    get_app_pixmap, get_category_icon, make_fluent_icon, normalize_text
)
from wintoolbox.ui.widgets.setting_card import SettingCard
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch


def make_launch_arrow_icon(normal_color: str = "#9ca3af", hover_color: str = "#ffffff", size: int = 14) -> QIcon:
    """Desenha um ícone vetorial nítido de seta diagonal ↗ via QPainter com estados normal e hover."""
    icon = QIcon()
    for col, mode in [(normal_color, QIcon.Normal), (hover_color, QIcon.Active)]:
        dpr = 2.0
        px = int(size * dpr)
        pix = QPixmap(px, px)
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.transparent)

        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(col), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

        s = float(size)
        p1 = s * 0.28
        p2 = s * 0.72
        # Linha diagonal
        p.drawLine(QPointF(p1, p2), QPointF(p2, p1))
        # Cabeça da seta
        bar = s * 0.28
        p.drawLine(QPointF(p2 - bar, p1), QPointF(p2, p1))
        p.drawLine(QPointF(p2, p1), QPointF(p2, p1 + bar))
        p.end()

        icon.addPixmap(pix, mode)
    return icon


def make_upload_pixmap(color: str = "#0078d4", size: int = 36) -> QPixmap:
    """Desenha um ícone vetorial limpo de bandeja de upload via QPainter (Zero Emojis)."""
    dpr = 2.0
    px = int(size * dpr)
    pix = QPixmap(px, px)
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)

    s = float(size)
    cx = s * 0.5
    # Seta para cima
    p.drawLine(QPointF(cx, s * 0.20), QPointF(cx, s * 0.62))
    p.drawLine(QPointF(cx - s * 0.20, s * 0.38), QPointF(cx, s * 0.20))
    p.drawLine(QPointF(cx + s * 0.20, s * 0.38), QPointF(cx, s * 0.20))
    # Bandeja inferior
    p.drawLine(QPointF(s * 0.20, s * 0.58), QPointF(s * 0.20, s * 0.80))
    p.drawLine(QPointF(s * 0.20, s * 0.80), QPointF(s * 0.80, s * 0.80))
    p.drawLine(QPointF(s * 0.80, s * 0.80), QPointF(s * 0.80, s * 0.58))
    p.end()

    return pix


class ToolCardWidget(QFrame):
    """Card interativo de ferramenta com cantos de 16px, botão circular ↗, modo Confortável/Compacto e Favorito."""
    clicked = Signal(str)
    favorite_toggled = Signal(str, bool)

    def __init__(self, tool: BaseTool, density: str = "comfortable", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.density = density
        self.setProperty("class", "tool-card")
        self.setCursor(Qt.PointingHandCursor)

        self._build_ui()

    def _build_ui(self) -> None:
        is_compact = self.density == "compact"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8 if is_compact else 12, 14, 8 if is_compact else 12)
        layout.setSpacing(6)

        r_top = QHBoxLayout()
        r_top.setSpacing(8)

        # Ícone da categoria vetorial nítido
        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_category_icon(self.tool.category, size=16).pixmap(16, 16))
        lbl_icon.setFixedSize(16, 16)
        r_top.addWidget(lbl_icon)

        # Nome da ferramenta
        lbl_name = QLabel(self.tool.name)
        lbl_name.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
        r_top.addWidget(lbl_name, stretch=1)

        # Badge de tipo (Lote vs Painel)
        is_batch = isinstance(self.tool, FileTool)
        lbl_badge = QLabel("Lote" if is_batch else "Painel")
        lbl_badge.setProperty("class", "badge-batch" if is_batch else "badge-panel")
        r_top.addWidget(lbl_badge)

        # Botão de Favorito discreto em ícone (sem texto invasivo)
        self.btn_fav = QPushButton()
        self.btn_fav.setProperty("class", "ghost")
        self.btn_fav.setFixedSize(24, 24)
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.clicked.connect(self._on_fav_clicked)
        self._refresh_fav_icon()
        r_top.addWidget(self.btn_fav)

        # Botão circular de disparo rápido com seta diagonal ↗
        self.btn_launch = QPushButton()
        self.btn_launch.setProperty("class", "action-circle-btn")
        self.btn_launch.setFixedSize(28, 28)
        self.btn_launch.setCursor(Qt.PointingHandCursor)
        self.btn_launch.setIcon(make_launch_arrow_icon(size=14))
        self.btn_launch.setToolTip(f"Abrir {self.tool.name}")
        self.btn_launch.clicked.connect(lambda: self.clicked.emit(self.tool.id))
        r_top.addWidget(self.btn_launch)

        layout.addLayout(r_top)

        if not is_compact:
            lbl_desc = QLabel(self.tool.description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setProperty("class", "secondary")
            layout.addWidget(lbl_desc)

            # Chips de extensões suportadas para ferramentas em lote
            if is_batch and getattr(self.tool, "accepts", None):
                exts = [e for e in self.tool.accepts if e]
                if exts:
                    r_exts = QHBoxLayout()
                    r_exts.setSpacing(4)
                    display_exts = exts[:3]
                    for ext in display_exts:
                        chip = QLabel(ext)
                        chip.setProperty("class", "ext-chip")
                        r_exts.addWidget(chip)
                    if len(exts) > 3:
                        more_chip = QLabel(f"+{len(exts) - 3}")
                        more_chip.setProperty("class", "ext-chip")
                        r_exts.addWidget(more_chip)
                    r_exts.addStretch()
                    layout.addLayout(r_exts)

    def _refresh_fav_icon(self) -> None:
        fav = is_favorite(self.self_tool_id)
        if fav:
            self.btn_fav.setIcon(make_fluent_icon("star_filled", "#eab308", size=14))
            self.btn_fav.setToolTip("Remover dos Favoritos")
        else:
            self.btn_fav.setIcon(make_fluent_icon("star", "#71717a", size=14))
            self.btn_fav.setToolTip("Adicionar aos Favoritos")

    @property
    def self_tool_id(self) -> str:
        return self.tool.id

    def _on_fav_clicked(self) -> None:
        new_state = toggle_favorite(self.tool.id)
        self._refresh_fav_icon()
        self.favorite_toggled.emit(self.tool.id, new_state)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.tool.id)
        super().mousePressEvent(event)


class SmartDropBanner(QFrame):
    """Smart Dropzone Bento Card integrado de arrastar e soltar arquivos ou pastas."""
    files_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Cabeçalho do Bento Card
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)

        lbl_title = QLabel("Smart Dropzone")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        hdr_row.addWidget(lbl_title)

        lbl_pill = QLabel("Arrastar e Soltar")
        lbl_pill.setProperty("class", "badge-pill")
        hdr_row.addWidget(lbl_pill)
        hdr_row.addStretch()

        layout.addLayout(hdr_row)

        # Área central com ícone vetorial de upload
        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(make_upload_pixmap(color="#0078d4", size=32))
        lbl_icon.setFixedSize(32, 32)
        lbl_icon.setAlignment(Qt.AlignCenter)
        mid_row.addWidget(lbl_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        lbl_main = QLabel("Solte arquivos ou pastas aqui")
        lbl_main.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        text_col.addWidget(lbl_main)

        lbl_sub = QLabel(
            "Suporta imagens, PDFs, vídeos, áudios, planilhas e processamento em lote."
        )
        lbl_sub.setProperty("class", "secondary")
        lbl_sub.setWordWrap(True)
        text_col.addWidget(lbl_sub)
        mid_row.addLayout(text_col, stretch=1)

        layout.addLayout(mid_row)

        # Botão estilo pill para seleção manual
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_pick = QPushButton("Selecionar Arquivos...")
        self.btn_pick.setCursor(Qt.PointingHandCursor)
        self.btn_pick.clicked.connect(self._on_pick_files)
        btn_row.addWidget(self.btn_pick)
        layout.addLayout(btn_row)

    def _on_pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos para Ação Rápida")
        if files:
            self.files_dropped.emit([Path(f) for f in files if Path(f).exists()])

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._on_pick_files()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("class", "dropzone dropzone-active")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("class", "dropzone")
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self.setProperty("class", "dropzone")
        self.style().unpolish(self)
        self.style().polish(self)
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if Path(u.toLocalFile()).exists()]
        if paths:
            self.files_dropped.emit(paths)


class SystemHealthBanner(QFrame):
    """System Telemetry Bento Card com medidores visuais e botão de ação rápida ↗."""
    open_monitor_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card bento-card")

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Cabeçalho: Título + Botão de Disparo ↗
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(make_fluent_icon("cat_system", "#a1a1aa", size=16).pixmap(16, 16))
        lbl_icon.setFixedSize(16, 16)
        hdr_row.addWidget(lbl_icon)

        lbl_title = QLabel("Telemetria do Sistema")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        hdr_row.addWidget(lbl_title)

        hdr_row.addStretch()

        self.btn_details = QPushButton()
        self.btn_details.setProperty("class", "action-circle-btn")
        self.btn_details.setFixedSize(28, 28)
        self.btn_details.setCursor(Qt.PointingHandCursor)
        self.btn_details.setIcon(make_launch_arrow_icon(size=14))
        self.btn_details.setToolTip("Abrir Monitor Detalhado do Sistema")
        self.btn_details.clicked.connect(self.open_monitor_requested.emit)
        hdr_row.addWidget(self.btn_details)

        layout.addLayout(hdr_row)

        # Medidor 1: Processador (CPU)
        col_cpu = QVBoxLayout()
        col_cpu.setSpacing(3)
        self.lbl_cpu = QLabel("Processador (CPU): 0%")
        self.lbl_cpu.setStyleSheet("font-size: 12px; font-weight: 500; background: transparent;")
        self.bar_cpu = QProgressBar()
        self.bar_cpu.setRange(0, 100)
        self.bar_cpu.setTextVisible(False)
        self.bar_cpu.setFixedHeight(7)
        col_cpu.addWidget(self.lbl_cpu)
        col_cpu.addWidget(self.bar_cpu)
        layout.addLayout(col_cpu)

        # Medidor 2: Memória RAM
        col_ram = QVBoxLayout()
        col_ram.setSpacing(3)
        self.lbl_ram = QLabel("Memória RAM: 0%")
        self.lbl_ram.setStyleSheet("font-size: 12px; font-weight: 500; background: transparent;")
        self.bar_ram = QProgressBar()
        self.bar_ram.setRange(0, 100)
        self.bar_ram.setTextVisible(False)
        self.bar_ram.setFixedHeight(7)
        col_ram.addWidget(self.lbl_ram)
        col_ram.addWidget(self.bar_ram)
        layout.addLayout(col_ram)

        # Medidor 3: Armazenamento (Disco)
        col_disk = QVBoxLayout()
        col_disk.setSpacing(3)
        self.lbl_disk = QLabel("Disco Principal: -")
        self.lbl_disk.setStyleSheet("font-size: 12px; font-weight: 500; background: transparent;")
        self.bar_disk = QProgressBar()
        self.bar_disk.setRange(0, 100)
        self.bar_disk.setTextVisible(False)
        self.bar_disk.setFixedHeight(7)
        col_disk.addWidget(self.lbl_disk)
        col_disk.addWidget(self.bar_disk)
        layout.addLayout(col_disk)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_metrics)

    def _apply_bar_style(self, bar: QProgressBar, val: int) -> None:
        """Aplica cantos arredondados e cor semântica à barra de progresso."""
        if val >= 90:
            color = "#ef4444"
        elif val >= 75:
            color = "#f59e0b"
        else:
            color = "#10b981"
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(128, 128, 128, 0.16);
                border: none;
                border-radius: 3px;
                height: 7px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)

    def refresh_metrics(self) -> None:
        try:
            m = collect_hardware_metrics()
            cpu_i = int(m.cpu_percent)
            self.lbl_cpu.setText(f"Processador (CPU): {cpu_i}% ({m.cpu_count} núcleos)")
            self.bar_cpu.setValue(cpu_i)
            self._apply_bar_style(self.bar_cpu, cpu_i)

            ram_i = int(m.mem_percent)
            self.lbl_ram.setText(f"Memória RAM: {m.mem_used_gb:.1f} / {m.mem_total_gb:.1f} GB ({ram_i}%)")
            self.bar_ram.setValue(ram_i)
            self._apply_bar_style(self.bar_ram, ram_i)

            if m.disks:
                d = m.disks[0]
                disk_i = int(d.percent)
                self.lbl_disk.setText(f"Disco ({d.mountpoint}): {d.free_gb:.1f} GB livres ({disk_i}% usado)")
                self.bar_disk.setValue(disk_i)
                self._apply_bar_style(self.bar_disk, disk_i)
        except Exception:
            pass

    def showEvent(self, event) -> None:
        self.refresh_metrics()
        self.timer.start(3000)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)


class HomeCustomizationDialog(QDialog):
    """Modal para o usuário personalizar os widgets e o layout da Tela Inicial Bento Grid."""
    layout_updated = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Personalizar Tela Inicial")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        hl = get_home_layout()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        lbl_title = QLabel("Personalizar Tela Inicial")
        lbl_title.setProperty("class", "title")
        root.addWidget(lbl_title)

        lbl_sub = QLabel("Escolha quais módulos Bento Grid e modos de visualização deseja exibir no seu painel inicial.")
        lbl_sub.setProperty("class", "secondary")
        lbl_sub.setWordWrap(True)
        root.addWidget(lbl_sub)

        # 1. Smart Dropzone
        self.sw_drop = ToggleSwitch()
        self.sw_drop.setChecked(bool(hl.get("show_smart_drop", True)))
        root.addWidget(SettingCard(
            "upload",
            "Smart Dropzone Bento Card",
            "Exibe a área integrada para arrastar arquivos e pastas e abrir ferramentas compatíveis.",
            self.sw_drop
        ))

        # 2. Mini-Monitor de Saúde do Sistema
        self.sw_health = ToggleSwitch()
        self.sw_health.setChecked(bool(hl.get("show_system_health", True)))
        root.addWidget(SettingCard(
            "cat_system",
            "Telemetria do Sistema (CPU, RAM e Disco)",
            "Exibe medidores de uso de hardware em tempo real no topo da tela inicial.",
            self.sw_health
        ))

        # 3. Favoritos e Recentes
        self.sw_favs = ToggleSwitch()
        self.sw_favs.setChecked(bool(hl.get("show_favorites_recents", True)))
        root.addWidget(SettingCard(
            "star_filled",
            "Acesso Rápido (Favoritos e Recentes)",
            "Destaca suas ferramentas favoritadas e as últimas utilizadas logo acima do catálogo.",
            self.sw_favs
        ))

        # 4. Densidade dos Cards
        self.cmb_density = QComboBox()
        self.cmb_density.addItems(["Confortável (Com descrição)", "Compacto (Alta densidade)"])
        self.cmb_density.setCurrentIndex(1 if hl.get("card_density") == "compact" else 0)
        root.addWidget(SettingCard(
            "grid",
            "Densidade dos Cartões de Ferramentas",
            "Alterne entre cartões detalhados ou cartões compactos de uma linha.",
            self.cmb_density
        ))

        # 5. Comportamento ao iniciar
        self.cmb_startup = QComboBox()
        self.cmb_startup.addItems(["Abrir Painel Inicial (Home)", "Reabrir Última Ferramenta Usada"])
        self.cmb_startup.setCurrentIndex(1 if hl.get("startup_view") == "last_tool" else 0)
        root.addWidget(SettingCard(
            "home",
            "Tela Padrão ao Iniciar o Aplicativo",
            "Define qual visão é aberta automaticamente quando o All the Utils inicia.",
            self.cmb_startup
        ))

        footer = QHBoxLayout()
        footer.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_save = QPushButton("Salvar Personalização")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._on_save)
        footer.addWidget(btn_save)
        root.addLayout(footer)

    def _on_save(self) -> None:
        update_home_layout({
            "show_smart_drop": self.sw_drop.isChecked(),
            "show_system_health": self.sw_health.isChecked(),
            "show_favorites_recents": self.sw_favs.isChecked(),
            "card_density": "compact" if self.cmb_density.currentIndex() == 1 else "comfortable",
            "startup_view": "last_tool" if self.cmb_startup.currentIndex() == 1 else "home",
        })
        self.layout_updated.emit()
        self.accept()


class HomePage(QWidget):
    """Visão inicial personalizável apresentando o dashboard Bento Grid e o catálogo de ferramentas."""
    tool_requested = Signal(str)        # tool_id
    favorite_changed = Signal()         # notifica MainWindow para sincronizar sidebar
    files_dropped = Signal(list)        # List[Path] para roteamento inteligente

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._selected_category: str = "ALL"
        self._search_query: str = ""
        self._current_columns: int = 2
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)

        self.content = QWidget()
        self.main_layout = QVBoxLayout(self.content)
        self.main_layout.setContentsMargins(24, 20, 24, 24)
        self.main_layout.setSpacing(18)

        # ── 1. Top Bento Tier Container (Hero Accent + Dropzone + Telemetria) ──
        self.bento_top_frame = QFrame()
        self.bento_top_layout = QGridLayout(self.bento_top_frame)
        self.bento_top_layout.setContentsMargins(0, 0, 0, 0)
        self.bento_top_layout.setSpacing(14)

        # 1.A. Hero Accent Card
        self.hero_card = QFrame()
        self.hero_card.setObjectName("heroCard")
        l_hero = QVBoxLayout(self.hero_card)
        l_hero.setContentsMargins(20, 16, 20, 16)
        l_hero.setSpacing(12)

        top_hero_row = QHBoxLayout()
        top_hero_row.setSpacing(12)

        lbl_hero_logo = QLabel()
        lbl_hero_logo.setPixmap(get_app_pixmap(44))
        lbl_hero_logo.setFixedSize(44, 44)
        lbl_hero_logo.setAlignment(Qt.AlignCenter)
        top_hero_row.addWidget(lbl_hero_logo)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(2)
        lbl_welcome = QLabel("WinToolbox — Produtividade")
        lbl_welcome.setProperty("class", "title")
        lbl_welcome.setStyleSheet("font-size: 16px; font-weight: 700; background: transparent;")
        hero_text_col.addWidget(lbl_welcome)

        total_count = len(get_all_tools())
        lbl_desc = QLabel(f"{total_count} ferramentas nativas com aceleração local.")
        lbl_desc.setProperty("class", "secondary")
        hero_text_col.addWidget(lbl_desc)
        top_hero_row.addLayout(hero_text_col, stretch=1)

        l_hero.addLayout(top_hero_row)

        # Pills informativos do Hero Bento
        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)

        pill_tools = QLabel(f"{total_count} Ferramentas")
        pill_tools.setProperty("class", "badge-pill")
        pills_row.addWidget(pill_tools)

        pill_shortcut = QLabel("Busca Rápida: Ctrl+K")
        pill_shortcut.setProperty("class", "badge-pill")
        pills_row.addWidget(pill_shortcut)

        pills_row.addStretch()

        self.btn_customize = QPushButton("Personalizar")
        self.btn_customize.setIcon(make_fluent_icon("settings", size=13))
        self.btn_customize.setCursor(Qt.PointingHandCursor)
        self.btn_customize.clicked.connect(self.open_customization_dialog)
        pills_row.addWidget(self.btn_customize)

        l_hero.addLayout(pills_row)

        # 1.B. Smart Dropzone Bento Card
        self.smart_drop_banner = SmartDropBanner(self)
        self.smart_drop_banner.files_dropped.connect(self.files_dropped.emit)

        # 1.C. System Telemetry Bento Card
        self.health_banner = SystemHealthBanner(self)
        self.health_banner.open_monitor_requested.connect(lambda: self.tool_requested.emit("system.monitor"))

        self.main_layout.addWidget(self.bento_top_frame)

        # ── 2. Container de Acesso Rápido (Favoritos e Recentes) ──
        self.quick_access_frame = QFrame()
        self.quick_access_frame.setProperty("class", "card")
        self.quick_access_layout = QVBoxLayout(self.quick_access_frame)
        self.quick_access_layout.setContentsMargins(18, 14, 18, 16)
        self.quick_access_layout.setSpacing(12)
        self.main_layout.addWidget(self.quick_access_frame)

        # ── 3. Barra de Controle do Catálogo (Busca + Densidade + Chips) ──
        catalog_ctrl = QVBoxLayout()
        catalog_ctrl.setSpacing(10)

        top_filter_row = QHBoxLayout()
        top_filter_row.setSpacing(10)

        lbl_cat_hdr = QLabel("Catálogo de Ferramentas")
        lbl_cat_hdr.setProperty("class", "section-title")
        lbl_cat_hdr.setStyleSheet("font-size: 15px; font-weight: 700; background: transparent;")
        top_filter_row.addWidget(lbl_cat_hdr)

        top_filter_row.addStretch()

        self.txt_home_search = QLineEdit()
        self.txt_home_search.setPlaceholderText("Filtrar ferramentas por nome, descrição ou extensão...")
        self.txt_home_search.setMinimumWidth(300)
        self.txt_home_search.textChanged.connect(self._on_search_changed)
        top_filter_row.addWidget(self.txt_home_search)

        self.btn_density_comf = QPushButton("Confortável")
        self.btn_density_comf.setCheckable(True)
        self.btn_density_comf.clicked.connect(lambda: self._set_density("comfortable"))
        top_filter_row.addWidget(self.btn_density_comf)

        self.btn_density_comp = QPushButton("Compacto")
        self.btn_density_comp.setCheckable(True)
        self.btn_density_comp.clicked.connect(lambda: self._set_density("compact"))
        top_filter_row.addWidget(self.btn_density_comp)

        catalog_ctrl.addLayout(top_filter_row)

        # Linha de Chips de Categoria com Scroll Horizontal Discreto
        chips_scroll = QScrollArea()
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFrameShape(QScrollArea.NoFrame)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        chips_scroll.setFixedHeight(38)

        chips_container = QWidget()
        self.chips_layout = QHBoxLayout(chips_container)
        self.chips_layout.setContentsMargins(0, 2, 0, 2)
        self.chips_layout.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self._build_category_chips()
        self.chips_layout.addStretch()
        chips_scroll.setWidget(chips_container)
        catalog_ctrl.addWidget(chips_scroll)

        self.main_layout.addLayout(catalog_ctrl)

        # ── 4. Container Dinâmico do Catálogo de Categorias ──
        self.catalog_container = QWidget()
        self.catalog_layout = QVBoxLayout(self.catalog_container)
        self.catalog_layout.setContentsMargins(0, 0, 0, 0)
        self.catalog_layout.setSpacing(16)
        self.main_layout.addWidget(self.catalog_container)

        self.main_layout.addStretch()
        self.scroll.setWidget(self.content)
        root_layout.addWidget(self.scroll)

        self.refresh_home()

    def _update_top_bento_layout(self, width: int) -> None:
        """Adapta a disposição dos cartões Bento da camada superior responsivamente."""
        # Remove os widgets do layout da grade sem destruí-los
        for i in reversed(range(self.bento_top_layout.count())):
            item = self.bento_top_layout.takeAt(i)
            if item.widget():
                item.widget().setParent(self.bento_top_frame)

        hl = get_home_layout()
        show_drop = bool(hl.get("show_smart_drop", True))
        show_health = bool(hl.get("show_system_health", True))

        self.smart_drop_banner.setVisible(show_drop)
        self.health_banner.setVisible(show_health)

        visible_cards = [self.hero_card]
        if show_drop:
            visible_cards.append(self.smart_drop_banner)
        if show_health:
            visible_cards.append(self.health_banner)

        count = len(visible_cards)
        if count == 1:
            self.bento_top_layout.addWidget(self.hero_card, 0, 0)
            self.bento_top_layout.setColumnStretch(0, 1)
        elif count == 2:
            if width >= 900:
                self.bento_top_layout.addWidget(visible_cards[0], 0, 0)
                self.bento_top_layout.addWidget(visible_cards[1], 0, 1)
                self.bento_top_layout.setColumnStretch(0, 1)
                self.bento_top_layout.setColumnStretch(1, 1)
            else:
                self.bento_top_layout.addWidget(visible_cards[0], 0, 0)
                self.bento_top_layout.addWidget(visible_cards[1], 1, 0)
                self.bento_top_layout.setColumnStretch(0, 1)
        elif count == 3:
            if width >= 1180:
                # 3 colunas lado a lado
                self.bento_top_layout.addWidget(self.hero_card, 0, 0)
                self.bento_top_layout.addWidget(self.smart_drop_banner, 0, 1)
                self.bento_top_layout.addWidget(self.health_banner, 0, 2)
                self.bento_top_layout.setColumnStretch(0, 12)
                self.bento_top_layout.setColumnStretch(1, 11)
                self.bento_top_layout.setColumnStretch(2, 11)
            elif width >= 860:
                # 2 linhas: Hero no topo (col 0-1), Dropzone e Telemetria abaixo
                self.bento_top_layout.addWidget(self.hero_card, 0, 0, 1, 2)
                self.bento_top_layout.addWidget(self.smart_drop_banner, 1, 0)
                self.bento_top_layout.addWidget(self.health_banner, 1, 1)
                self.bento_top_layout.setColumnStretch(0, 1)
                self.bento_top_layout.setColumnStretch(1, 1)
            else:
                # Empilhado verticalmente
                self.bento_top_layout.addWidget(self.hero_card, 0, 0)
                self.bento_top_layout.addWidget(self.smart_drop_banner, 1, 0)
                self.bento_top_layout.addWidget(self.health_banner, 2, 0)
                self.bento_top_layout.setColumnStretch(0, 1)

    def _build_category_chips(self) -> None:
        categories = get_categories()
        total = len(get_all_tools())

        btn_all = QPushButton(f"Todas ({total})")
        btn_all.setProperty("class", "chip")
        btn_all.setCheckable(True)
        btn_all.setChecked(True)
        btn_all.clicked.connect(lambda: self._on_category_selected("ALL"))
        self.chip_group.addButton(btn_all)
        self.chips_layout.addWidget(btn_all)

        for cat_name, tools in categories.items():
            btn = QPushButton(f"{cat_name} ({len(tools)})")
            btn.setProperty("class", "chip")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, c=cat_name: self._on_category_selected(c))
            self.chip_group.addButton(btn)
            self.chips_layout.addWidget(btn)

    def _on_category_selected(self, category: str) -> None:
        self._selected_category = category
        self._render_catalog()

    def _on_search_changed(self, text: str) -> None:
        self._search_query = normalize_text(text)
        self._render_catalog()

    def _set_density(self, density: str) -> None:
        update_home_layout({"card_density": density})
        self.refresh_home()

    def open_customization_dialog(self) -> None:
        dlg = HomeCustomizationDialog(self)
        dlg.layout_updated.connect(self.refresh_home)
        dlg.exec()

    def _calculate_columns(self, density: str) -> int:
        w = self.width()
        if density == "compact":
            if w >= 1280:
                return 4
            if w >= 900:
                return 3
            return 2
        else:
            if w >= 1350:
                return 4
            if w >= 1020:
                return 3
            return 2

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_top_bento_layout(self.width())
        hl = get_home_layout()
        density = hl.get("card_density", "comfortable")
        new_cols = self._calculate_columns(density)
        if new_cols != self._current_columns:
            self._current_columns = new_cols
            self._render_quick_access(hl)
            self._render_catalog()

    def refresh_home(self) -> None:
        """Recarrega a visibilidade dos módulos e renderiza os cartões conforme as preferências."""
        hl = get_home_layout()
        density = hl.get("card_density", "comfortable")
        self._current_columns = self._calculate_columns(density)

        self.btn_density_comf.setChecked(density == "comfortable")
        self.btn_density_comp.setChecked(density == "compact")

        self._update_top_bento_layout(self.width())

        self._render_quick_access(hl)
        self._render_catalog()

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _render_quick_access(self, hl: Dict) -> None:
        self._clear_layout(self.quick_access_layout)
        if not hl.get("show_favorites_recents", True):
            self.quick_access_frame.setVisible(False)
            return

        st = load_settings()
        fav_ids = st.get("favorites", [])
        recent_ids = [r for r in st.get("recent_tools", []) if r not in fav_ids][:6]

        fav_tools = [get_tool(tid) for tid in fav_ids if get_tool(tid) is not None]
        rec_tools = [get_tool(tid) for tid in recent_ids if get_tool(tid) is not None]

        if not fav_tools and not rec_tools:
            self.quick_access_frame.setVisible(False)
            return

        self.quick_access_frame.setVisible(True)
        cols = max(2, self._current_columns)

        if fav_tools:
            lbl_fav = QLabel(f"Favoritos Fixados ({len(fav_tools)})")
            lbl_fav.setProperty("class", "section-title")
            lbl_fav.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
            self.quick_access_layout.addWidget(lbl_fav)

            grid_fav = QGridLayout()
            grid_fav.setHorizontalSpacing(12)
            grid_fav.setVerticalSpacing(10)
            for idx, tool in enumerate(fav_tools):
                card = ToolCardWidget(tool, density="compact")
                card.clicked.connect(self.tool_requested.emit)
                card.favorite_toggled.connect(self._on_card_fav_toggled)
                grid_fav.addWidget(card, idx // cols, idx % cols)
            self.quick_access_layout.addLayout(grid_fav)

        if rec_tools:
            lbl_rec = QLabel("Usados Recentemente")
            lbl_rec.setProperty("class", "section-title")
            lbl_rec.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
            self.quick_access_layout.addWidget(lbl_rec)

            grid_rec = QGridLayout()
            grid_rec.setHorizontalSpacing(12)
            grid_rec.setVerticalSpacing(10)
            for idx, tool in enumerate(rec_tools):
                card = ToolCardWidget(tool, density="compact")
                card.clicked.connect(self.tool_requested.emit)
                card.favorite_toggled.connect(self._on_card_fav_toggled)
                grid_rec.addWidget(card, idx // cols, idx % cols)
            self.quick_access_layout.addLayout(grid_rec)

    def _render_catalog(self) -> None:
        self._clear_layout(self.catalog_layout)
        hl = get_home_layout()
        density = hl.get("card_density", "comfortable")
        cols = max(2, self._current_columns)
        q = getattr(self, "_search_query", "")

        categories = get_categories()
        any_rendered = False

        cat_items = list(categories.items())
        # Quando há busca ativa, ordena as categorias pela relevância máxima das ferramentas encontradas
        if q:
            def cat_max_score(cat_tuple):
                _, tools = cat_tuple
                scores = [calculate_tool_relevance(t, q) for t in tools]
                return max(scores) if scores else 0
            cat_items.sort(key=cat_max_score, reverse=True)

        for cat_name, tools in cat_items:
            if self._selected_category != "ALL" and cat_name != self._selected_category:
                continue

            if q:
                ranked = search_and_rank_tools(tools, q)
                filtered_tools: List[BaseTool] = [t for t, score in ranked if score > 0]
            else:
                filtered_tools = tools

            if not filtered_tools:
                continue

            any_rendered = True
            cat_group = QFrame()
            cat_group.setProperty("class", "card")
            cat_layout = QVBoxLayout(cat_group)
            cat_layout.setContentsMargins(18, 14, 18, 16)
            cat_layout.setSpacing(12)

            r_cat_hdr = QHBoxLayout()
            r_cat_hdr.setSpacing(8)

            lbl_cat_icon = QLabel()
            lbl_cat_icon.setPixmap(get_category_icon(cat_name, size=16).pixmap(16, 16))
            lbl_cat_icon.setFixedSize(16, 16)
            r_cat_hdr.addWidget(lbl_cat_icon)

            lbl_cat = QLabel(f"{cat_name} ({len(filtered_tools)})")
            lbl_cat.setProperty("class", "section-title")
            lbl_cat.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
            r_cat_hdr.addWidget(lbl_cat)
            r_cat_hdr.addStretch()
            cat_layout.addLayout(r_cat_hdr)

            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(10)

            for idx, t in enumerate(filtered_tools):
                card = ToolCardWidget(t, density=density)
                card.clicked.connect(self.tool_requested.emit)
                card.favorite_toggled.connect(self._on_card_fav_toggled)
                grid.addWidget(card, idx // cols, idx % cols)

            cat_layout.addLayout(grid)
            self.catalog_layout.addWidget(cat_group)

        if not any_rendered:
            empty_card = QFrame()
            empty_card.setProperty("class", "card")
            l_emp = QVBoxLayout(empty_card)
            l_emp.setContentsMargins(24, 24, 24, 24)
            lbl_emp = QLabel(f"Nenhuma ferramenta encontrada para '{q}'.\nTente buscar pelo nome da ação, tecnologia ou extensão de arquivo.")
            lbl_emp.setProperty("class", "secondary")
            lbl_emp.setAlignment(Qt.AlignCenter)
            l_emp.addWidget(lbl_emp)
            self.catalog_layout.addWidget(empty_card)

    def _on_card_fav_toggled(self, tool_id: str, is_fav: bool) -> None:
        self._render_quick_access(get_home_layout())
        self.favorite_changed.emit()
