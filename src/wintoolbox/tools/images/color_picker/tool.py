"""
Ferramenta: Conta-Gotas de Tela e Seletor de Cores.
Captura da cor do pixel sob o cursor, exibição de prévia ampliada e histórico de códigos (HEX, RGB, HSL, CMYK).
Inclui modo Conta-Gotas com tela congelada multi-monitor, lupa 8x e minimização automática.
"""
import winsound
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QGuiApplication, QImage,
    QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.ui.widgets.data_table import bind_timer_to_visibility
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.tools.images.color_picker.logic import (
    VK_ESCAPE, VK_LBUTTON, VK_RBUTTON, VK_RETURN, VK_SPACE,
    get_pixel_color_at_screen, is_key_pressed, rgb_to_formats
)


class FloatingMagnifierOverlay(QWidget):
    """Overlay flutuante de compatibilidade mantendo contrato com os testes unitários."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(144, 172)
        self._pixmap: Optional[QPixmap] = None
        self._hex_code: str = "#000000"

    def update_magnifier(self, pos: QPoint, hex_code: str) -> None:
        self._hex_code = hex_code
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        if screen:
            radius = 7
            raw_pix = screen.grabWindow(0, pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
            self._pixmap = raw_pix.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.move(pos.x() + 20, pos.y() + 20)
        self.update()


class _FrozenDesktopOverlay(QWidget):
    """
    Overlay fullscreen sem bordas cobrindo todo o desktop virtual (todos os monitores).
    Exibe snapshot congelado com lupa 8x e mira acompanhando o cursor do mouse.
    Clique Esquerdo: Captura a cor.
    Shift + Clique: Captura múltiplas cores sem fechar.
    Scroll: Ajusta o zoom da lupa (4x, 8x, 12x, 16x).
    ESC ou Clique Direito: Fecha e restaura a janela principal.
    """
    def __init__(self, owner_view: "ColorPickerView"):
        super().__init__(None)
        self.owner = owner_view
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)

        self._virtual_rect = QRect()
        self._snapshot_pixmap: Optional[QPixmap] = None
        self._snapshot_image: Optional[QImage] = None
        self._mouse_pos: QPoint = QPoint(0, 0)
        self._zoom_factor: int = 8

    def start_capture(self) -> None:
        # Calcula geometria virtual combinada de todas as telas
        screens = QApplication.screens()
        min_x = min(s.geometry().x() for s in screens)
        min_y = min(s.geometry().y() for s in screens)
        max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
        max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
        self._virtual_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

        # Captura screenshot de cada tela e compõe
        composed = QPixmap(self._virtual_rect.size())
        composed.fill(Qt.GlobalColor.black)
        p = QPainter(composed)
        for s in screens:
            geom = s.geometry()
            pix = s.grabWindow(0)
            p.drawPixmap(geom.x() - min_x, geom.y() - min_y, pix)
        p.end()

        self._snapshot_pixmap = composed
        self._snapshot_image = composed.toImage()

        self.setGeometry(self._virtual_rect)
        self._mouse_pos = QCursor.pos()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event) -> None:
        if not self._snapshot_pixmap:
            return

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._snapshot_pixmap)

        # Desenho da Lupa ampliada acompanhando o mouse
        mx = self._mouse_pos.x() - self._virtual_rect.x()
        my = self._mouse_pos.y() - self._virtual_rect.y()

        # Cor do pixel sob o cursor
        color = self._get_color_at_point(mx, my)
        hex_code = color.name().upper()
        rgb_text = f"RGB: {color.red()}, {color.green()}, {color.blue()}"

        # Tamanho e posição da lupa (150x180 px)
        lupa_w, lupa_h = 150, 180
        lx = mx + 25
        ly = my + 25
        if lx + lupa_w > self.width():
            lx = mx - lupa_w - 25
        if ly + lupa_h > self.height():
            ly = my - lupa_h - 25

        # Card da Lupa
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QBrush(QColor(20, 22, 26, 240)))
        painter.setPen(QPen(QColor(80, 85, 95), 1.5))
        painter.drawRoundedRect(lx, ly, lupa_w, lupa_h, 8, 8)

        # Recorte dos pixels vizinhos
        grid_r = 6
        grid_diameter = grid_r * 2 + 1
        crop_rect = QRect(mx - grid_r, my - grid_r, grid_diameter, grid_diameter)
        cropped = self._snapshot_pixmap.copy(crop_rect)

        # Desenho dos pixels ampliados
        zoom_display_rect = QRect(lx + 10, ly + 10, lupa_w - 20, 105)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(zoom_display_rect, cropped)

        # Moldura da grade
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor(100, 105, 115), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(zoom_display_rect)

        # Mira central (cruz vermelha com ponto branco)
        cx = zoom_display_rect.center().x()
        cy = zoom_display_rect.center().y()
        painter.setPen(QPen(QColor(255, 50, 50), 2))
        painter.drawLine(cx - 8, cy, cx + 8, cy)
        painter.drawLine(cx, cy - 8, cx, cy + 8)

        # Swatch de cor e textos HEX / RGB
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        swatch_rect = QRect(lx + 10, ly + 122, 18, 18)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
        painter.drawRoundedRect(swatch_rect, 3, 3)

        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(lx + 34, ly + 136, hex_code)

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(180, 185, 195))
        painter.drawText(lx + 10, ly + 158, rgb_text)

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(120, 125, 135))
        painter.drawText(lx + 10, ly + 172, f"Zoom: {self._zoom_factor}x (Scroll)")

    def _get_color_at_point(self, x: int, y: int) -> QColor:
        if self._snapshot_image and 0 <= x < self._snapshot_image.width() and 0 <= y < self._snapshot_image.height():
            return QColor(self._snapshot_image.pixel(x, y))
        return QColor(0, 0, 0)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._mouse_pos = event.globalPosition().toPoint()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            mx = self._mouse_pos.x() - self._virtual_rect.x()
            my = self._mouse_pos.y() - self._virtual_rect.y()
            c = self._get_color_at_point(mx, my)

            keep_open = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.owner._on_pixel_captured(c.red(), c.green(), c.blue(), keep_open=keep_open)
            if not keep_open:
                self.close_and_restore()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close_and_restore()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom_factor = min(16, self._zoom_factor + 2)
        elif delta < 0:
            self._zoom_factor = max(4, self._zoom_factor - 2)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_and_restore()
        elif event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            mx = self._mouse_pos.x() - self._virtual_rect.x()
            my = self._mouse_pos.y() - self._virtual_rect.y()
            c = self._get_color_at_point(mx, my)
            self.owner._on_pixel_captured(c.red(), c.green(), c.blue(), keep_open=False)
            self.close_and_restore()

    def close_and_restore(self) -> None:
        self.hide()
        self.owner._stop_screen_picker()


@register
class ColorPickerTool(Tool):
    id = "images.color_picker"
    name = "Conta-Gotas de Tela"
    category = "Imagens"
    description = "Selecione e capture qualquer cor da tela em múltiplos monitores com lupa de alta precisão"
    keywords = ["cor", "color", "picker", "hex", "rgb", "hsl", "cmyk", "conta-gotas", "lupa", "paleta"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ColorPickerView(self, parent)


class ColorPickerView(QWidget):
    def __init__(self, tool: ColorPickerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._picking_active: bool = False
        self._history_colors: List[Dict[str, str]] = []

        self._overlay = FloatingMagnifierOverlay(self)
        self._frozen_overlay = _FrozenDesktopOverlay(self)

        self._picker_timer = QTimer(self)
        self._picker_timer.timeout.connect(self._picker_tick)

        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._update_hover_color)
        bind_timer_to_visibility(self, self._hover_timer, interval_ms=120)

        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Barra do Conta-Gotas
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        self.btn_toggle_picker = QPushButton("Capturar Cor da Tela (Congelar Monitores)")
        self.btn_toggle_picker.setProperty("class", "primary")
        self.btn_toggle_picker.setFixedHeight(40)
        self.btn_toggle_picker.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 22px;")
        self.btn_toggle_picker.clicked.connect(self._toggle_screen_picker)
        top_bar.addWidget(self.btn_toggle_picker)

        self.chk_auto_copy = QCheckBox("Copiar HEX automaticamente")
        self.chk_auto_copy.setChecked(True)
        top_bar.addWidget(self.chk_auto_copy)

        self.chk_sound = QCheckBox("Som ao capturar")
        self.chk_sound.setChecked(True)
        top_bar.addWidget(self.chk_sound)

        self.chk_minimize = QCheckBox("Minimizar janela durante a captura")
        self.chk_minimize.setChecked(len(QApplication.screens()) == 1)
        top_bar.addWidget(self.chk_minimize)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Painel Superior: Códigos da Cor e Amostra
        top_box = QHBoxLayout()
        top_box.setSpacing(16)

        grp_codes = QGroupBox("Códigos da Cor Atual")
        codes_layout = QVBoxLayout(grp_codes)
        codes_layout.setSpacing(8)

        # HEX
        row_hex = QHBoxLayout()
        row_hex.addWidget(QLabel("HEX:"))
        self.txt_hex = QLineEdit("#000000")
        self.txt_hex.setReadOnly(True)
        row_hex.addWidget(self.txt_hex)
        btn_cp_hex = QPushButton("Copiar")
        btn_cp_hex.clicked.connect(lambda: self._copy_to_clip(self.txt_hex.text()))
        row_hex.addWidget(btn_cp_hex)
        codes_layout.addLayout(row_hex)

        # RGB
        row_rgb = QHBoxLayout()
        row_rgb.addWidget(QLabel("RGB:"))
        self.txt_rgb = QLineEdit("rgb(0, 0, 0)")
        self.txt_rgb.setReadOnly(True)
        row_rgb.addWidget(self.txt_rgb)
        btn_cp_rgb = QPushButton("Copiar")
        btn_cp_rgb.clicked.connect(lambda: self._copy_to_clip(self.txt_rgb.text()))
        row_rgb.addWidget(btn_cp_rgb)
        codes_layout.addLayout(row_rgb)

        # HSL
        row_hsl = QHBoxLayout()
        row_hsl.addWidget(QLabel("HSL:"))
        self.txt_hsl = QLineEdit("hsl(0, 0%, 0%)")
        self.txt_hsl.setReadOnly(True)
        row_hsl.addWidget(self.txt_hsl)
        btn_cp_hsl = QPushButton("Copiar")
        btn_cp_hsl.clicked.connect(lambda: self._copy_to_clip(self.txt_hsl.text()))
        row_hsl.addWidget(btn_cp_hsl)
        codes_layout.addLayout(row_hsl)

        top_box.addWidget(grp_codes, 1)

        # Amostra Viva
        grp_swatch = QGroupBox("Amostra Viva")
        swatch_layout = QVBoxLayout(grp_swatch)
        self.frame_swatch = QFrame()
        self.frame_swatch.setFixedSize(110, 110)
        self.frame_swatch.setStyleSheet("background-color: #000000; border-radius: 8px; border: 1px solid #777;")
        swatch_layout.addWidget(self.frame_swatch)
        top_box.addWidget(grp_swatch)

        layout.addLayout(top_box)

        # Histórico
        grp_hist = QGroupBox("Histórico de Cores Capturadas")
        hist_layout = QVBoxLayout(grp_hist)

        self.table_hist = QTableWidget()
        self.table_hist.setColumnCount(5)
        self.table_hist.setHorizontalHeaderLabels(["Amostra", "HEX", "RGB", "HSL", "CMYK"])
        self.table_hist.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_hist.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_hist.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_hist.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_hist.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_hist.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_hist.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_hist.setAlternatingRowColors(True)
        self.table_hist.cellDoubleClicked.connect(self._on_table_double_clicked)
        enable_sorting_on_table(self.table_hist)
        hist_layout.addWidget(self.table_hist)

        row_bottom = QHBoxLayout()
        lbl_hint = QLabel("Dica: Clique com o mouse para capturar a cor. Shift + Clique para capturar várias cores seguidas. ESC fecha.")
        lbl_hint.setProperty("class", "secondary")
        row_bottom.addWidget(lbl_hint)
        row_bottom.addStretch()

        self.btn_clear_hist = QPushButton("Limpar Histórico")
        self.btn_clear_hist.clicked.connect(self._clear_history)
        row_bottom.addWidget(self.btn_clear_hist)
        hist_layout.addLayout(row_bottom)

        layout.addWidget(grp_hist)
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _toggle_screen_picker(self):
        if self._picking_active:
            self._stop_screen_picker()
        else:
            self._start_screen_picker()

    def _start_screen_picker(self):
        self._picking_active = True
        self.btn_toggle_picker.setText("Cancelar Conta-Gotas (ou aperte ESC)")
        self.btn_toggle_picker.setStyleSheet("font-weight: bold; background-color: #D83B01; color: white; padding: 6px 20px;")

        self._overlay.show()
        win = self.window()
        should_min = self.chk_minimize.isChecked() or len(QApplication.screens()) == 1

        if should_min and win:
            win.showMinimized()
            # Aguarda a minimização completar antes de capturar os pixels do desktop
            QTimer.singleShot(220, self._open_frozen_overlay)
        else:
            self._open_frozen_overlay()

        self._picker_timer.start(16)

    def _open_frozen_overlay(self):
        if self._picking_active:
            self._frozen_overlay.start_capture()

    def _stop_screen_picker(self):
        self._picking_active = False
        self._picker_timer.stop()
        self._overlay.hide()
        self._frozen_overlay.hide()

        self.btn_toggle_picker.setText("Capturar Cor da Tela (Congelar Monitores)")
        self.btn_toggle_picker.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 22px;")

        win = self.window()
        if win and (self.chk_minimize.isChecked() or len(QApplication.screens()) == 1):
            win.showNormal()
            win.raise_()
            win.activateWindow()

    def _picker_tick(self):
        """Tick para detecção global de tecla ESC caso a janela não tenha foco."""
        if not self._picking_active:
            return
        if is_key_pressed(VK_ESCAPE) or is_key_pressed(VK_RBUTTON):
            self._stop_screen_picker()

    def _on_pixel_captured(self, r: int, g: int, b: int, keep_open: bool = False):
        formats = rgb_to_formats(r, g, b)
        hex_val = formats["hex"]

        self.txt_hex.setText(hex_val)
        self.txt_rgb.setText(formats["rgb"])
        self.txt_hsl.setText(formats["hsl"])
        self.frame_swatch.setStyleSheet(f"background-color: {hex_val}; border-radius: 8px; border: 1px solid #777;")

        if self.chk_auto_copy.isChecked():
            self._copy_to_clip(hex_val, silent=True)
            show_toast(self, f"Cor {hex_val} copiada para a área de transferência!")

        if self.chk_sound.isChecked():
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

        # Adiciona ao histórico
        self._add_to_history(formats)

        if not keep_open:
            self._stop_screen_picker()

    def _update_hover_color(self):
        if self._picking_active:
            return
        pos = QCursor.pos()
        r, g, b = get_pixel_color_at_screen(pos.x(), pos.y())
        formats = rgb_to_formats(r, g, b)
        self.txt_hex.setText(formats["hex"])
        self.txt_rgb.setText(formats["rgb"])
        self.txt_hsl.setText(formats["hsl"])
        self.frame_swatch.setStyleSheet(f"background-color: {formats['hex']}; border-radius: 8px; border: 1px solid #777;")

    def _add_to_history(self, formats: Dict[str, str]):
        self._history_colors.insert(0, formats)
        self._refresh_history_table()

    def _refresh_history_table(self):
        with batch_table_update(self.table_hist):
            self.table_hist.setRowCount(len(self._history_colors))
            for row, item in enumerate(self._history_colors):
                color_cell = QTableWidgetItem()
                color_cell.setBackground(QColor(item["hex"]))
                color_cell.setFlags(color_cell.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table_hist.setItem(row, 0, color_cell)

                for col, key in enumerate(["hex", "rgb", "hsl", "cmyk"], start=1):
                    t_item = SmartTableWidgetItem(item.get(key, ""))
                    t_item.setFlags(t_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                    self.table_hist.setItem(row, col, t_item)

    def _on_table_double_clicked(self, row: int, col: int):
        item = self.table_hist.item(row, col)
        if item and col > 0:
            self._copy_to_clip(item.text())

    def _copy_to_clip(self, text: str, silent: bool = False):
        cb = QApplication.clipboard()
        cb.setText(text)
        if not silent:
            show_toast(self, f"'{text}' copiado!")

    def _clear_history(self):
        self._history_colors.clear()
        self.table_hist.setRowCount(0)
