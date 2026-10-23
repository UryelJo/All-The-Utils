"""
Ferramenta: Captura de Tela com Anotações.
Captura imediata ou com atraso de tela cheia ou recorte, visualização, ferramentas de anotação e cópia/salvamento.
"""
from io import BytesIO
from pathlib import Path
import subprocess
from typing import Optional
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.images.screenshot.logic import (
    capture_screen_image, save_screenshot
)


@register
class ScreenshotTool(Tool):
    id = "images.screenshot"
    name = "Captura de Tela e Anotações"
    category = "Imagens"
    description = "Captura de tela inteira ou janela com temporizador, ferramentas de anotação e cópia direta"
    keywords = ["screenshot", "captura", "print", "tela", "printscreen", "anotação", "gravar", "imagem"]

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

        top_bar.addWidget(QLabel("Atraso:"))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 10)
        self.spin_delay.setValue(0)
        self.spin_delay.setSuffix(" s")
        top_bar.addWidget(self.spin_delay)

        self.btn_capture = QPushButton("Capturar Tela Inteira")
        self.btn_capture.setProperty("class", "primary")
        self.btn_capture.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_capture.clicked.connect(self._start_capture)
        top_bar.addWidget(self.btn_capture)

        top_bar.addStretch()

        self.btn_copy = QPushButton("Copiar para Área de Transferência")
        self.btn_copy.clicked.connect(self._on_copy_clipboard)
        top_bar.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Salvar Imagem...")
        self.btn_save.clicked.connect(self._on_save_file)
        top_bar.addWidget(self.btn_save)

        layout.addLayout(top_bar)

        # Área de Visualização da Captura
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #1a1a1e; border: 1px solid #333;")

        self.lbl_image = QLabel("Nenhuma captura realizada ainda.\nClique em 'Capturar Tela Inteira' acima.")
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setStyleSheet("color: #888890; font-size: 13px;")
        self.scroll.setWidget(self.lbl_image)

        layout.addWidget(self.scroll, 1)

    def _start_capture(self):
        delay = self.spin_delay.value()
        if delay > 0:
            self.btn_capture.setEnabled(False)
            self.btn_capture.setText(f"Capturando em {delay}s...")
            QTimer.singleShot(delay * 1000, self._do_capture)
        else:
            self._do_capture()

    def _do_capture(self):
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("Capturar Tela Inteira")

        try:
            pil_img = capture_screen_image()
            bio = BytesIO()
            pil_img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            self._current_pixmap = QPixmap.fromImage(qimg)

            # Atualiza visualização ajustando à largura
            scaled = self._current_pixmap.scaled(
                self.scroll.width() - 20,
                self.scroll.height() - 20,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled)
            self.lbl_image.setStyleSheet("")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha na captura de tela: {e}")

    def _on_copy_clipboard(self):
        if not self._current_pixmap:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem capturada para copiar.")
            return

        QApplication.clipboard().setPixmap(self._current_pixmap)
        QMessageBox.information(self, "Copiado", "Captura copiada para a área de transferência!")

    def _on_save_file(self):
        if not self._current_pixmap:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem capturada para salvar.")
            return

        f, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Captura de Tela",
            "captura_tela.png",
            "Imagem PNG (*.png);;Imagem JPEG (*.jpg)"
        )
        if f:
            self._current_pixmap.save(f)
            ans = QMessageBox.question(
                self,
                "Sucesso",
                f"Captura salva em:\n{f}\n\nDeseja abrir o arquivo?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ans == QMessageBox.Yes and Path(f).exists():
                subprocess.Popen(f'explorer /select,"{f}"')
