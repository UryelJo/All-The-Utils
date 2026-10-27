"""
Ferramenta: Conta-Gotas de Tela e Seletor de Cores.
Captura da cor do pixel sob o cursor, exibição de prévia ampliada e histórico de códigos (HEX, RGB, HSL, CMYK).
Inclui modo Conta-Gotas com Lupa Flutuante (PowerToys style) e captura global por Espaço ou Clique em qualquer aplicativo.
"""
import winsound
from typing import Optional
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
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
    """
    Overlay flutuante de lupa (estilo PowerToys Color Picker).
    Acompanha o cursor do mouse sobre qualquer janela ou aplicativo do Windows
    (WhatsApp, navegadores, jogos, etc.) sem roubar o foco ativo, exibindo a
    grade de pixels com zoom 8x, mira central de precisão e código HEX em tempo real.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(144, 172)

        self._pixmap: Optional[QPixmap] = None
        self._hex_code: str = "#000000"

    def update_magnifier(self, pos: QPoint, hex_code: str) -> None:
        self._hex_code = hex_code

        # Captura recorte de 14x14 pixels ao redor do cursor e amplia
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        if screen:
            radius = 7
            raw_pix = screen.grabWindow(0, pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
            self._pixmap = raw_pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.FastTransformation)
        else:
            self._pixmap = None

        # Posicionamento inteligente (evita sair das bordas do monitor)
        geom = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        target_x = pos.x() + 20
        target_y = pos.y() + 20

        if target_x + self.width() > geom.right() - 5:
            target_x = pos.x() - self.width() - 20
        if target_y + self.height() > geom.bottom() - 5:
            target_y = pos.y() - self.height() - 20

        self.move(target_x, target_y)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 1. Cartão com cantos arredondados translúcido e borda elegante
        card_rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(QBrush(QColor(24, 24, 28, 235)))
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1.5))
        painter.drawRoundedRect(card_rect, 10, 10)

        # 2. Desenho do Pixmap da Lupa ampliada
        zoom_rect = QRect(12, 12, 120, 105)
        if self._pixmap:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            painter.drawPixmap(zoom_rect, self._pixmap)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Borda da lupa
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(80, 80, 90), 1))
        painter.drawRect(zoom_rect)

        # Mira central de precisão (vermelho vivo com contorno branco)
        cx = zoom_rect.center().x()
        cy = zoom_rect.center().y()
        painter.setPen(QPen(QColor(0, 0, 0, 180), 2))
        painter.drawRect(cx - 5, cy - 5, 10, 10)
        painter.setPen(QPen(QColor(255, 50, 50), 1.5))
        painter.drawRect(cx - 5, cy - 5, 10, 10)

        # 3. Amostra de cor e Código HEX
        swatch_rect = QRect(14, 124, 18, 18)
        painter.setBrush(QBrush(QColor(self._hex_code)))
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
        painter.drawRoundedRect(swatch_rect, 4, 4)

        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(QRect(38, 123, 94, 20), Qt.AlignLeft | Qt.AlignVCenter, self._hex_code)

        # Dica rápida no rodapé
        font_hint = QFont("Segoe UI", 7)
        painter.setFont(font_hint)
        painter.setPen(QPen(QColor(180, 180, 190)))
        painter.drawText(QRect(12, 146, 120, 16), Qt.AlignCenter, "Espaço/Clique | Esc")
        painter.end()


@register
class ColorPickerTool(Tool):
    id = "images.color_picker"
    name = "Conta-Gotas de Tela e Seletor de Cores"
    category = "Imagens"
    description = (
        "Captura de cores de qualquer pixel na tela sobre qualquer aplicativo (WhatsApp, navegadores, jogos) "
        "com lupa flutuante de zoom, captura por Espaço/Clique global e histórico nos formatos HEX, RGB, HSL e CMYK."
    )
    keywords = ["cor", "color", "picker", "hex", "rgb", "hsl", "cmyk", "conta-gotas", "pixel", "paleta", "eyedropper"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ColorPickerView(self, parent)


class ColorPickerView(QWidget):
    def __init__(self, tool: ColorPickerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._history = []
        self._picking_active = False
        self._last_captured_hex = ""
        self._space_was_down = False

        # Lupa flutuante independente (HUD)
        self._overlay = FloatingMagnifierOverlay()

        self._build_ui()

        # Timer padrão para atualizar a lupa fixa da janela quando visível (10x/segundo)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_hover_color)
        bind_timer_to_visibility(self, self.timer, 100)

        # Timer de alta frequência (60 FPS) para o modo Conta-Gotas ativo com captura global
        self._picker_timer = QTimer(self)
        self._picker_timer.timeout.connect(self._picker_tick)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 0. Barra Superior de Ação Principal: Botão Proeminente de Conta-Gotas Flutuante
        banner_box = QFrame()
        banner_box.setProperty("class", "card")
        banner_layout = QHBoxLayout(banner_box)
        banner_layout.setContentsMargins(14, 12, 14, 12)
        banner_layout.setSpacing(16)

        self.btn_toggle_picker = QPushButton("🎯 Iniciar Conta-Gotas na Tela (Espaço ou Clique em Qualquer App)")
        self.btn_toggle_picker.setProperty("class", "primary")
        self.btn_toggle_picker.setMinimumHeight(42)
        self.btn_toggle_picker.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 20px;")
        self.btn_toggle_picker.clicked.connect(self._toggle_screen_picker)
        banner_layout.addWidget(self.btn_toggle_picker)

        # Opções rápidas de captura
        self.chk_auto_copy = QCheckBox("Copiar HEX automaticamente ao capturar")
        self.chk_auto_copy.setChecked(True)
        banner_layout.addWidget(self.chk_auto_copy)

        self.chk_sound = QCheckBox("Tocar som de confirmação")
        self.chk_sound.setChecked(True)
        banner_layout.addWidget(self.chk_sound)

        self.chk_minimize = QCheckBox("Minimizar janela durante captura")
        self.chk_minimize.setChecked(False)
        banner_layout.addWidget(self.chk_minimize)

        banner_layout.addStretch()
        layout.addWidget(banner_box)

        # 1. Painel Superior: Lupa de Zoom e Cor Atual
        top_box = QHBoxLayout()
        top_box.setSpacing(16)

        # Lupa / Preview
        grp_zoom = QGroupBox("Lupa de Zoom (Pixel Sob o Cursor)")
        zoom_layout = QVBoxLayout(grp_zoom)
        self.lbl_zoom = QLabel()
        self.lbl_zoom.setFixedSize(120, 120)
        self.lbl_zoom.setStyleSheet("border: 2px solid #555; background-color: #000; border-radius: 4px;")
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        zoom_layout.addWidget(self.lbl_zoom)
        top_box.addWidget(grp_zoom)

        # Preview e Códigos
        grp_codes = QGroupBox("Formatos de Cores do Pixel Atual")
        codes_layout = QVBoxLayout(grp_codes)
        codes_layout.setSpacing(6)

        row_hex = QHBoxLayout()
        row_hex.addWidget(QLabel("HEX:"))
        self.txt_hex = QLineEdit("#000000")
        self.txt_hex.setReadOnly(True)
        row_hex.addWidget(self.txt_hex)
        btn_cp_hex = QPushButton("Copiar")
        btn_cp_hex.clicked.connect(lambda: self._copy_to_clip(self.txt_hex.text()))
        row_hex.addWidget(btn_cp_hex)
        codes_layout.addLayout(row_hex)

        row_rgb = QHBoxLayout()
        row_rgb.addWidget(QLabel("RGB:"))
        self.txt_rgb = QLineEdit("rgb(0, 0, 0)")
        self.txt_rgb.setReadOnly(True)
        row_rgb.addWidget(self.txt_rgb)
        btn_cp_rgb = QPushButton("Copiar")
        btn_cp_rgb.clicked.connect(lambda: self._copy_to_clip(self.txt_rgb.text()))
        row_rgb.addWidget(btn_cp_rgb)
        codes_layout.addLayout(row_rgb)

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

        # Bloco com a Cor Viva
        grp_swatch = QGroupBox("Amostra Viva")
        swatch_layout = QVBoxLayout(grp_swatch)
        self.frame_swatch = QFrame()
        self.frame_swatch.setFixedSize(110, 110)
        self.frame_swatch.setStyleSheet("background-color: #000000; border-radius: 8px; border: 1px solid #777;")
        swatch_layout.addWidget(self.frame_swatch)
        top_box.addWidget(grp_swatch)

        layout.addLayout(top_box)

        # 2. Histórico de Cores Capturadas
        grp_hist = QGroupBox("Histórico de Cores Capturadas")
        hist_layout = QVBoxLayout(grp_hist)

        self.table_hist = QTableWidget()
        self.table_hist.setColumnCount(5)
        self.table_hist.setHorizontalHeaderLabels(["Amostra", "HEX", "RGB", "HSL", "CMYK"])
        self.table_hist.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_hist.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_hist.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_hist.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_hist.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_hist.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_hist.setSelectionMode(QTableWidget.SingleSelection)
        self.table_hist.setAlternatingRowColors(True)
        self.table_hist.cellDoubleClicked.connect(self._on_table_double_clicked)
        enable_sorting_on_table(self.table_hist)
        hist_layout.addWidget(self.table_hist)

        # Rodapé da tabela
        row_bottom = QHBoxLayout()
        lbl_hint = QLabel("💡 Dica: Dê dois cliques em qualquer linha para copiar o código. Aperte ESPAÇO a qualquer momento para capturar!")
        lbl_hint.setProperty("class", "secondary")
        row_bottom.addWidget(lbl_hint)
        row_bottom.addStretch()

        self.btn_clear_hist = QPushButton("Limpar Histórico")
        self.btn_clear_hist.clicked.connect(self._clear_history)
        row_bottom.addWidget(self.btn_clear_hist)
        hist_layout.addLayout(row_bottom)

        layout.addWidget(grp_hist)

    def _toggle_screen_picker(self):
        if self._picking_active:
            self._stop_screen_picker()
        else:
            self._start_screen_picker()

    def _start_screen_picker(self):
        self._picking_active = True
        self.btn_toggle_picker.setText("⏹ Cancelar Conta-Gotas (ou aperte ESC)")
        self.btn_toggle_picker.setStyleSheet("font-weight: bold; background-color: #D83B01; color: white; padding: 6px 20px;")

        if self.chk_minimize.isChecked():
            win = self.window()
            if win:
                win.showMinimized()

        self._overlay.show()
        self._picker_timer.start(16)  # ~60 FPS para rastreamento suave

    def _stop_screen_picker(self):
        self._picking_active = False
        self._picker_timer.stop()
        self._overlay.hide()

        self.btn_toggle_picker.setText("🎯 Iniciar Conta-Gotas na Tela (Espaço ou Clique em Qualquer App)")
        self.btn_toggle_picker.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 20px;")

        if self.chk_minimize.isChecked():
            win = self.window()
            if win:
                win.showNormal()
                win.raise_()
                win.activateWindow()

    def _picker_tick(self):
        """Tick a 60 FPS durante o modo Conta-Gotas flutuante: atualiza a lupa e detecta teclas/cliques globais."""
        if not self._picking_active:
            return

        pos = QCursor.pos()
        r, g, b = get_pixel_color_at_screen()
        formats = rgb_to_formats(r, g, b)

        # Atualiza a janela flutuante
        self._overlay.update_magnifier(pos, formats["hex"])

        # 1. Cancelamento por ESC ou Botão Direito do Mouse
        if is_key_pressed(VK_ESCAPE) or is_key_pressed(VK_RBUTTON):
            self._stop_screen_picker()
            return

        # 2. Confirmação e Captura por ESPAÇO, ENTER ou CLIQUE ESQUERDO DO MOUSE em qualquer app
        if is_key_pressed(VK_SPACE) or is_key_pressed(VK_RETURN) or is_key_pressed(VK_LBUTTON):
            self._capture_current_pixel()
            self._stop_screen_picker()
            return

    def _update_hover_color(self):
        """Atualização periódica (100ms) quando a ferramenta estiver aberta na tela."""
        pos = QCursor.pos()
        r, g, b = get_pixel_color_at_screen()
        formats = rgb_to_formats(r, g, b)

        self.txt_hex.setText(formats["hex"])
        self.txt_rgb.setText(formats["rgb"])
        self.txt_hsl.setText(formats["hsl"])
        self.frame_swatch.setStyleSheet(f"background-color: {formats['hex']}; border-radius: 8px; border: 1px solid #777;")

        # Renderiza Lupa interna da janela
        screen = QGuiApplication.primaryScreen()
        if screen:
            radius = 10
            pix = screen.grabWindow(0, pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
            scaled = pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.FastTransformation)

            painter = QPainter(scaled)
            painter.setPen(QPen(QColor(0, 0, 0, 180), 2))
            painter.drawRect(55, 55, 10, 10)
            painter.setPen(QPen(QColor(255, 50, 50), 1.5))
            painter.drawRect(55, 55, 10, 10)
            painter.end()

            self.lbl_zoom.setPixmap(scaled)

        # Detecção global de tecla Espaço mesmo sem a lupa flutuante estar explicitamente iniciada!
        # Isso garante que se o usuário estiver com o WinToolbox aberto e o mouse no WhatsApp, apertar Espaço captura!
        space_down = is_key_pressed(VK_SPACE)
        if space_down and not self._space_was_down and not self._picking_active:
            self._capture_current_pixel()
        self._space_was_down = space_down

    def _capture_current_pixel(self):
        r, g, b = get_pixel_color_at_screen()
        formats = rgb_to_formats(r, g, b)

        # Evita duplicata se for idêntica à última capturada
        if self._history and self._history[0]["hex"] == formats["hex"]:
            # Mesmo sendo igual, dá o feedback sonoro e copia se requisitado
            self._trigger_feedback(formats["hex"])
            return

        self._history.insert(0, formats)
        self._refresh_history_table()
        self._trigger_feedback(formats["hex"])

    def _trigger_feedback(self, hex_code: str):
        # 1. Copia automática para o Clipboard
        if self.chk_auto_copy.isChecked():
            QApplication.clipboard().setText(hex_code)

        # 2. Som de confirmação do Windows
        if self.chk_sound.isChecked():
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

        # 3. Toast visual
        try:
            show_toast(self, "Cor Capturada!", f"{hex_code} copiado para a Área de Transferência.", "success", 2500)
        except Exception:
            pass

    def _refresh_history_table(self):
        with batch_table_update(self.table_hist):
            self.table_hist.setRowCount(len(self._history))
            for row, item in enumerate(self._history):
                swatch_item = SmartTableWidgetItem("      ", sort_value=item["hex"])
                swatch_item.setBackground(QColor(item["hex"]))
                self.table_hist.setItem(row, 0, swatch_item)

                self.table_hist.setItem(row, 1, SmartTableWidgetItem(item["hex"]))
                self.table_hist.setItem(row, 2, SmartTableWidgetItem(item["rgb"]))
                self.table_hist.setItem(row, 3, SmartTableWidgetItem(item["hsl"]))
                self.table_hist.setItem(row, 4, SmartTableWidgetItem(item["cmyk"]))

    def _on_table_double_clicked(self, row: int, col: int):
        item = self.table_hist.item(row, col)
        if item and col > 0:
            self._copy_to_clip(item.text())

    def _copy_to_clip(self, text: str):
        if text:
            QApplication.clipboard().setText(text)
            try:
                show_toast(self, "Copiado!", f"{text} copiado para a Área de Transferência.", "info", 2000)
            except Exception:
                QMessageBox.information(self, "Copiado", f"Código copiado para a área de transferência:\n{text}")

    def _clear_history(self):
        self._history.clear()
        self.table_hist.setRowCount(0)

    def closeEvent(self, event):
        self._stop_screen_picker()
        self._overlay.close()
        super().closeEvent(event)

    def hideEvent(self, event):
        self._stop_screen_picker()
        super().hideEvent(event)
