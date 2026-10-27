"""
Interface gráfica do Extrator de Texto da Tela (Text Extractor estilo PowerToys).
"""
import io
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.text_extractor.logic import extract_text_from_image_region
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("images.text_extractor.ui")


class ScreenSnipperOverlay(QDialog):
    """Janela sobreposta em tela cheia para seleção retangular da região a ser copiada."""

    def __init__(self, on_region_selected, parent=None):
        super().__init__(parent, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.on_region_selected = on_region_selected
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        self._start_pt: Optional[QPoint] = None
        self._current_pt: Optional[QPoint] = None
        self._is_selecting = False

        # Cobre todas as telas
        screen = QGuiApplication.primaryScreen()
        geo = screen.virtualGeometry() if hasattr(screen, "virtualGeometry") else screen.geometry()
        self.setGeometry(geo)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_pt = event.globalPosition().toPoint()
            self._current_pt = self._start_pt
            self._is_selecting = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.reject()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_pt = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            p1 = self._start_pt
            p2 = event.globalPosition().toPoint()
            self.close()

            if p1 and p2:
                r = QRect(p1, p2).normalized()
                if r.width() > 5 and r.height() > 5:
                    self.on_region_selected(r)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self._is_selecting and self._start_pt and self._current_pt:
            r = QRect(self._start_pt, self._current_pt).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(r, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            pen = QPen(QColor(96, 165, 250), 2)
            painter.setPen(pen)
            painter.drawRect(r)


@register
class TextExtractorTool(Tool):
    id = "images.text_extractor"
    name = "Extrator de Texto de Tela"
    category = "Imagens"
    description = "Capture qualquer região da tela e copie instantaneamente o texto via OCR WinRT para a área de transferência"
    keywords = ["ocr", "texto", "tela", "capturar", "copiar", "extrator", "powertoys", "snipping", "leitor"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TextExtractorView(self, parent)


class TextExtractorView(QWidget):
    def __init__(self, tool: TextExtractorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Cartão de Ações Principais
        action_card = QFrame()
        action_card.setObjectName("Card")
        a_lay = QHBoxLayout(action_card)
        a_lay.setContentsMargins(16, 14, 16, 14)
        a_lay.setSpacing(12)

        self.btn_capture = QPushButton("Capturar Região da Tela")
        self.btn_capture.setProperty("accent", True)
        self.btn_capture.setMinimumHeight(38)
        self.btn_capture.clicked.connect(self._start_screen_capture)
        a_lay.addWidget(self.btn_capture)

        self.btn_paste = QPushButton("Colar Imagem (Ctrl+V)")
        self.btn_paste.setMinimumHeight(38)
        self.btn_paste.clicked.connect(self._paste_image)
        a_lay.addWidget(self.btn_paste)

        self.btn_file = QPushButton("Abrir Arquivo de Imagem...")
        self.btn_file.setMinimumHeight(38)
        self.btn_file.clicked.connect(self._open_file)
        a_lay.addWidget(self.btn_file)

        a_lay.addStretch(1)

        self.lbl_status = QLabel("Pronto para capturar.")
        self.lbl_status.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 11px;")
        a_lay.addWidget(self.lbl_status)

        root.addWidget(action_card)

        # Área de Texto Reconhecido
        text_card = QFrame()
        text_card.setObjectName("Card")
        t_lay = QVBoxLayout(text_card)
        t_lay.setContentsMargins(16, 14, 16, 14)
        t_lay.setSpacing(8)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(QLabel("<b>Texto Reconhecido pelo OCR:</b>"))
        hdr_row.addStretch(1)

        self.btn_copy_text = QPushButton("Copiar Texto")
        self.btn_copy_text.clicked.connect(self._copy_text)
        hdr_row.addWidget(self.btn_copy_text)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.clicked.connect(self._clear_text)
        hdr_row.addWidget(self.btn_clear)

        t_lay.addLayout(hdr_row)

        self.txt_result = QPlainTextEdit()
        self.txt_result.setFont(QFont("Segoe UI", 10))
        self.txt_result.setPlaceholderText("O texto reconhecido aparecerá aqui e será automaticamente copiado para a sua área de transferência...")
        t_lay.addWidget(self.txt_result)

        root.addWidget(text_card, stretch=1)

    def _start_screen_capture(self) -> None:
        # Oculta temporariamente a janela principal para não interferir no print
        window = self.window()
        if window:
            window.showMinimized()

        # Pequeno atraso para a animação de minimizar do Windows terminar
        QTimer.singleShot(350, self._show_overlay)

    def _show_overlay(self) -> None:
        self.overlay = ScreenSnipperOverlay(self._on_region_captured)
        self.overlay.show()

    def _on_region_captured(self, rect: QRect) -> None:
        # Restaura a janela
        window = self.window()
        if window:
            window.showNormal()
            window.activateWindow()

        screen = QGuiApplication.primaryScreen()
        if not screen:
            return

        pix = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        self._process_pixmap(pix)

    def _paste_image(self) -> None:
        clipboard = QApplication.clipboard()
        pix = clipboard.pixmap()
        if not pix or pix.isNull():
            show_toast(self, "Nenhuma imagem encontrada na área de transferência.", duration_ms=2500)
            return
        self._process_pixmap(pix)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para OCR",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tiff);;Todos os Arquivos (*.*)"
        )
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                self._process_pixmap(pix)

    def _process_pixmap(self, pix: QPixmap) -> None:
        self.lbl_status.setText("Processando OCR com o motor nativo...")
        self.btn_capture.setEnabled(False)

        # Converte QPixmap para PIL Image em memória
        image_bytes = io.BytesIO()
        pix.save(image_bytes, "PNG")
        image_bytes.seek(0)
        pil_img = Image.open(image_bytes)

        def worker(ctx) -> str:
            return extract_text_from_image_region(pil_img)

        def on_done(text: str) -> None:
            self.btn_capture.setEnabled(True)
            self.lbl_status.setText("Texto extraído com sucesso!")
            self.txt_result.setPlainText(text)

            if text:
                QApplication.clipboard().setText(text)
                show_toast(self, "Texto copiado para a área de transferência!", duration_ms=3000)
            else:
                show_toast(self, "Nenhum texto detectado na região selecionada.", duration_ms=2500)

        def on_error(err: Exception) -> None:
            self.btn_capture.setEnabled(True)
            self.lbl_status.setText("Erro no processamento do OCR.")
            _log.error(f"Erro no OCR: {err}")
            show_toast(self, f"Falha no OCR: {err}", duration_ms=3000)

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _copy_text(self) -> None:
        text = self.txt_result.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            show_toast(self, "Texto copiado!", duration_ms=2000)

    def _clear_text(self) -> None:
        self.txt_result.clear()
        self.lbl_status.setText("Pronto para capturar.")
