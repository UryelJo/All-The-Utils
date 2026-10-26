"""
Ferramenta: Conta-Gotas de Tela e Seletor de Cores.
Captura da cor do pixel sob o cursor, exibição de prévia ampliada e histórico de códigos (HEX, RGB, HSL, CMYK).
"""
from typing import Optional
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.ui.widgets.data_table import bind_timer_to_visibility
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)
from wintoolbox.tools.images.color_picker.logic import (
    get_pixel_color_at_screen, rgb_to_formats
)


@register
class ColorPickerTool(Tool):
    id = "images.color_picker"
    name = "Conta-Gotas de Tela e Seletor de Cores"
    category = "Imagens"
    description = "Captura de cores de qualquer pixel na tela com lupa de zoom e histórico nos formatos HEX, RGB e HSL"
    keywords = ["cor", "color", "picker", "hex", "rgb", "hsl", "cmyk", "conta-gotas", "pixel", "paleta"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ColorPickerView(self, parent)


class ColorPickerView(QWidget):
    def __init__(self, tool: ColorPickerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._history = []
        self._build_ui()

        # Timer para atualizar a lupa em tempo real quando o mouse estiver sobre o widget ou monitorando
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_hover_color)
        # Captura a tela 10x/s: só enquanto a ferramenta estiver visível
        bind_timer_to_visibility(self, self.timer, 100)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. Painel Superior: Lupa de Zoom e Cor Atual
        top_box = QHBoxLayout()
        top_box.setSpacing(16)

        # Lupa / Preview
        grp_zoom = QGroupBox("Lupa de Zoom (Pixel Atual)")
        zoom_layout = QVBoxLayout(grp_zoom)
        self.lbl_zoom = QLabel()
        self.lbl_zoom.setFixedSize(120, 120)
        self.lbl_zoom.setStyleSheet("border: 2px solid #555; background-color: #000;")
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        zoom_layout.addWidget(self.lbl_zoom)
        top_box.addWidget(grp_zoom)

        # Preview e Códigos
        grp_codes = QGroupBox("Códigos da Cor Sob o Cursor")
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
        grp_swatch = QGroupBox("Amostra")
        swatch_layout = QVBoxLayout(grp_swatch)
        self.frame_swatch = QFrame()
        self.frame_swatch.setFixedSize(100, 100)
        self.frame_swatch.setStyleSheet("background-color: #000000; border-radius: 6px; border: 1px solid #777;")
        swatch_layout.addWidget(self.frame_swatch)
        top_box.addWidget(grp_swatch)

        layout.addLayout(top_box)

        # Botão de Captura
        btn_bar = QHBoxLayout()
        self.btn_capture = QPushButton("Capturar Cor Sob o Cursor Agora (Espaço ou Clique)")
        self.btn_capture.setProperty("class", "primary")
        self.btn_capture.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.btn_capture.clicked.connect(self._capture_current_pixel)
        btn_bar.addWidget(self.btn_capture)

        btn_bar.addStretch()

        self.btn_clear_hist = QPushButton("Limpar Histórico")
        self.btn_clear_hist.clicked.connect(self._clear_history)
        btn_bar.addWidget(self.btn_clear_hist)

        layout.addLayout(btn_bar)

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

        layout.addWidget(grp_hist)

    def _update_hover_color(self):
        pos = QCursor.pos()
        r, g, b = get_pixel_color_at_screen()
        formats = rgb_to_formats(r, g, b)

        self.txt_hex.setText(formats["hex"])
        self.txt_rgb.setText(formats["rgb"])
        self.txt_hsl.setText(formats["hsl"])
        self.frame_swatch.setStyleSheet(f"background-color: {formats['hex']}; border-radius: 6px; border: 1px solid #777;")

        # Renderiza Lupa (zoom 5x dos pixels ao redor)
        screen = QGuiApplication.primaryScreen()
        if screen:
            radius = 12
            pix = screen.grabWindow(0, pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
            scaled = pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.FastTransformation)

            # Desenha mira central na lupa
            painter = QPainter(scaled)
            painter.setPen(Qt.red)
            painter.drawRect(55, 55, 10, 10)
            painter.end()

            self.lbl_zoom.setPixmap(scaled)

    def _capture_current_pixel(self):
        pos = QCursor.pos()
        r, g, b = get_pixel_color_at_screen()
        formats = rgb_to_formats(r, g, b)

        # Evita duplicata se for idêntica à última capturada
        if self._history and self._history[0]["hex"] == formats["hex"]:
            return

        self._history.insert(0, formats)
        self._refresh_history_table()

    def _refresh_history_table(self):
        with batch_table_update(self.table_hist):
            self.table_hist.setRowCount(len(self._history))
            for row, item in enumerate(self._history):
                # Amostra visual
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
            QMessageBox.information(self, "Copiado", f"Código copiado para a área de transferência:\n{text}")

    def _clear_history(self):
        self._history.clear()
        self.table_hist.setRowCount(0)
