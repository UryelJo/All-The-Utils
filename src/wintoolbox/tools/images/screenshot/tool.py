"""
Ferramenta: Captura de Tela e Visualizador com Zoom.
Suporta seleção individual de monitores, resoluções alvo pré-definidas,
temporizador de atraso e visualizador de alta resolução com zoom e pan.
"""
from io import BytesIO
from pathlib import Path
from typing import Optional
from PIL import Image

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.images.screenshot.logic import (
    capture_screen_image, save_screenshot
)
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.zoomable_image import ZoomableImageCanvas


@register
class ScreenshotTool(Tool):
    id = "images.screenshot"
    name = "Captura de Tela"
    category = "Imagens"
    description = "Captura de tela inteira ou por monitor com temporizador, escala de resolução e zoom"
    keywords = ["screenshot", "captura", "print", "tela", "printscreen", "monitor", "imagem"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ScreenshotView(self, parent)


class ScreenshotView(QWidget):
    def __init__(self, tool: ScreenshotTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_pixmap: Optional[QPixmap] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra Superior de Controles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        # Seletor de Monitor
        top_bar.addWidget(QLabel("Monitor:"))
        self.cmb_monitor = QComboBox()
        self._populate_monitors()
        top_bar.addWidget(self.cmb_monitor)

        # Resolução Alvo
        top_bar.addWidget(QLabel("Resolução Alvo:"))
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItem("Nativa do Monitor (100%)", "native")
        self.cmb_resolution.addItem("Full HD (1920 × 1080)", (1920, 1080))
        self.cmb_resolution.addItem("HD (1280 × 720)", (1280, 720))
        self.cmb_resolution.addItem("Escala 75%", 0.75)
        self.cmb_resolution.addItem("Escala 50%", 0.50)
        top_bar.addWidget(self.cmb_resolution)

        # Atraso
        top_bar.addWidget(QLabel("Atraso:"))
        self.spin_delay = SliderSpinControl("", 0, 15, 0, suffix=" s")
        self.spin_delay.setFixedWidth(130)
        top_bar.addWidget(self.spin_delay)

        self.btn_capture = QPushButton("Capturar Tela")
        self.btn_capture.setProperty("class", "primary")
        self.btn_capture.setFixedHeight(32)
        self.btn_capture.setStyleSheet("font-weight: bold; padding: 4px 18px;")
        self.btn_capture.clicked.connect(self._start_capture)
        top_bar.addWidget(self.btn_capture)

        top_bar.addStretch()

        self.btn_copy = QPushButton("Copiar para Área de Transferência")
        self.btn_copy.setFixedHeight(32)
        self.btn_copy.clicked.connect(self._on_copy_clipboard)
        top_bar.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Salvar Imagem...")
        self.btn_save.setFixedHeight(32)
        self.btn_save.clicked.connect(self._on_save_file)
        top_bar.addWidget(self.btn_save)

        layout.addLayout(top_bar)

        # Canvas com Zoom e Pan
        self.canvas = ZoomableImageCanvas(self)
        layout.addWidget(self.canvas, stretch=1)

    def _populate_monitors(self):
        self.cmb_monitor.clear()
        screens = QApplication.screens()
        self.cmb_monitor.addItem("Todos os Monitores (Área Virtual)", -1)
        for idx, s in enumerate(screens):
            g = s.geometry()
            name = f"Monitor {idx + 1}"
            if s == QApplication.primaryScreen():
                name += " (Principal)"
            name += f" — {g.width()}×{g.height()} px"
            self.cmb_monitor.addItem(name, idx)

    def _start_capture(self):
        delay = int(self.spin_delay.value())
        if delay > 0:
            self.btn_capture.setEnabled(False)
            self._remaining_delay = delay
            self.btn_capture.setText(f"Capturando em {self._remaining_delay}s...")
            self._timer_delay = QTimer(self)
            self._timer_delay.timeout.connect(self._on_delay_tick)
            self._timer_delay.start(1000)
        else:
            self._do_capture()

    def _on_delay_tick(self):
        self._remaining_delay -= 1
        if self._remaining_delay <= 0:
            self._timer_delay.stop()
            self.btn_capture.setEnabled(True)
            self.btn_capture.setText("Capturar Tela")
            self._do_capture()
        else:
            self.btn_capture.setText(f"Capturando em {self._remaining_delay}s...")

    def _do_capture(self):
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("Capturar Tela")

        screens = QApplication.screens()
        selected_idx = self.cmb_monitor.currentData()

        if selected_idx == -1 or selected_idx >= len(screens):
            # Área virtual completa
            min_x = min(s.geometry().x() for s in screens)
            min_y = min(s.geometry().y() for s in screens)
            max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
            max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
            bbox = (min_x, min_y, max_x, max_y)
        else:
            s = screens[selected_idx]
            g = s.geometry()
            bbox = (g.x(), g.y(), g.x() + g.width(), g.y() + g.height())

        try:
            im = capture_screen_image(bbox)

            # Aplica resolução alvo
            res_opt = self.cmb_resolution.currentData()
            if isinstance(res_opt, tuple):
                im = im.resize(res_opt, Image.Resampling.LANCZOS)
            elif isinstance(res_opt, float):
                nw = max(1, int(im.width * res_opt))
                nh = max(1, int(im.height * res_opt))
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)

            # Converte para QPixmap
            import io
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue())
            self._current_pixmap = pix
            self.canvas.set_pixmap(pix, auto_fit=True)
            show_toast(self, "Captura realizada com sucesso!")
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Falha na captura: {ex}")

    def _on_copy_clipboard(self):
        if not self._current_pixmap:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem capturada para copiar.")
            return
        cb = QApplication.clipboard()
        cb.setPixmap(self._current_pixmap)
        show_toast(self, "Imagem copiada para a área de transferência!")

    def _on_save_file(self):
        if not self._current_pixmap:
            QMessageBox.warning(self, "Aviso", "Nenhuma captura disponível para salvar.")
            return

        dest_str, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Captura de Tela",
            "captura.png",
            "PNG (*.png);;JPEG (*.jpg);;WEBP (*.webp)"
        )
        if dest_str:
            self._current_pixmap.save(dest_str)
            show_toast(self, f"Captura salva em:\n{dest_str}")
