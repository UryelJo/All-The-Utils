"""
Canvas visualizador de imagem com suporte a zoom interativo, pan (arraste),
fundo xadrez para transparência e seleção de região (ROI / crop).
"""
from typing import Optional, Tuple
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QMouseEvent, QPainter, QPaintEvent,
    QPen, QPixmap, QWheelEvent
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)


class _CanvasView(QWidget):
    """Área interna de renderização com zoom e pan contínuos."""
    roiChanged = Signal(QRect)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap: Optional[QPixmap] = None
        self._zoom: float = 1.0
        self._pan_offset: QPoint = QPoint(0, 0)
        self._last_mouse_pos: QPoint = QPoint()
        self._is_panning: bool = False

        self._show_checkerboard: bool = True
        self._enable_roi_selection: bool = False
        self._roi_rect: Optional[QRect] = None  # em coordenadas reais da imagem
        self._roi_start: Optional[QPoint] = None  # início do arraste ROI
        self._is_selecting_roi: bool = False

        # Fundo xadrez pré-renderizado
        self._checker_brush = self._create_checker_brush()

    @staticmethod
    def _create_checker_brush() -> QBrush:
        size = 16
        pix = QPixmap(size, size)
        p = QPainter(pix)
        c1 = QColor(240, 240, 240)
        c2 = QColor(215, 215, 215)
        p.fillRect(0, 0, size // 2, size // 2, c1)
        p.fillRect(size // 2, 0, size // 2, size // 2, c2)
        p.fillRect(0, size // 2, size // 2, size // 2, c1)
        p.fillRect(size // 2, size // 2, size // 2, size // 2, c2)
        p.end()
        return QBrush(pix)

    def set_pixmap(self, pixmap: Optional[QPixmap], auto_fit: bool = True) -> None:
        self._pixmap = pixmap
        self._roi_rect = None
        if auto_fit:
            self.fit_to_view()
        else:
            self.update()

    def set_checkerboard_enabled(self, enabled: bool) -> None:
        self._show_checkerboard = enabled
        self.update()

    def set_roi_selection_enabled(self, enabled: bool) -> None:
        self._enable_roi_selection = enabled
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.update()

    def get_roi(self) -> Optional[QRect]:
        return self._roi_rect

    def set_roi(self, rect: Optional[QRect]) -> None:
        self._roi_rect = rect
        self.update()
        if rect:
            self.roiChanged.emit(rect)

    def clear_roi(self) -> None:
        self._roi_rect = None
        self.update()

    def fit_to_view(self) -> None:
        if not self._pixmap or self._pixmap.isNull() or self.width() <= 10 or self.height() <= 10:
            self._zoom = 1.0
            self._pan_offset = QPoint(0, 0)
            self.update()
            return

        w_ratio = (self.width() - 20) / self._pixmap.width()
        h_ratio = (self.height() - 20) / self._pixmap.height()
        self._zoom = max(0.02, min(w_ratio, h_ratio, 4.0))

        # Centraliza
        rendered_w = int(self._pixmap.width() * self._zoom)
        rendered_h = int(self._pixmap.height() * self._zoom)
        self._pan_offset = QPoint((self.width() - rendered_w) // 2, (self.height() - rendered_h) // 2)
        self.update()

    def set_zoom_level(self, zoom: float) -> None:
        zoom = max(0.05, min(zoom, 16.0))
        # Ajusta offset para manter o centro
        if self._pixmap:
            center_x = self.width() / 2
            center_y = self.height() / 2
            # Ponto correspondente na imagem
            img_x = (center_x - self._pan_offset.x()) / self._zoom
            img_y = (center_y - self._pan_offset.y()) / self._zoom

            self._zoom = zoom
            new_offset_x = int(center_x - img_x * self._zoom)
            new_offset_y = int(center_y - img_y * self._zoom)
            self._pan_offset = QPoint(new_offset_x, new_offset_y)
        else:
            self._zoom = zoom
        self.update()

    def zoom_in(self) -> None:
        self.set_zoom_level(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom_level(self._zoom / 1.25)

    def zoom_100(self) -> None:
        self.set_zoom_level(1.0)

    # Conversão de coordenadas
    def screen_to_image_coords(self, pt: QPoint) -> QPoint:
        if not self._pixmap or self._zoom == 0:
            return QPoint(0, 0)
        ix = int((pt.x() - self._pan_offset.x()) / self._zoom)
        iy = int((pt.y() - self._pan_offset.y()) / self._zoom)
        return QPoint(
            max(0, min(ix, self._pixmap.width())),
            max(0, min(iy, self._pixmap.height()))
        )

    def image_to_screen_rect(self, rect: QRect) -> QRect:
        sx = int(rect.x() * self._zoom + self._pan_offset.x())
        sy = int(rect.y() * self._zoom + self._pan_offset.y())
        sw = int(rect.width() * self._zoom)
        sh = int(rect.height() * self._zoom)
        return QRect(sx, sy, sw, sh)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Fundo do canvas
        painter.fillRect(self.rect(), QColor(25, 27, 30))

        if not self._pixmap or self._pixmap.isNull():
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Nenhuma imagem selecionada")
            return

        img_w = int(self._pixmap.width() * self._zoom)
        img_h = int(self._pixmap.height() * self._zoom)
        dst_rect = QRect(self._pan_offset.x(), self._pan_offset.y(), img_w, img_h)

        # Xadrez para fundo transparente
        if self._show_checkerboard:
            painter.fillRect(dst_rect, self._checker_brush)

        # Desenho da imagem interpolada
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._zoom <= 3.0)
        painter.drawPixmap(dst_rect, self._pixmap)

        # Borda sutil na imagem
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawRect(dst_rect)

        # Desenho de ROI (seleção pontilhada)
        if self._roi_rect and not self._roi_rect.isEmpty():
            s_rect = self.image_to_screen_rect(self._roi_rect)
            pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 150, 255, 35))
            painter.drawRect(s_rect)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return

        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        new_zoom = max(0.05, min(self._zoom * factor, 16.0))

        mouse_pos = event.position().toPoint()
        img_x = (mouse_pos.x() - self._pan_offset.x()) / self._zoom
        img_y = (mouse_pos.y() - self._pan_offset.y()) / self._zoom

        self._zoom = new_zoom
        new_offset_x = int(mouse_pos.x() - img_x * self._zoom)
        new_offset_y = int(mouse_pos.y() - img_y * self._zoom)
        self._pan_offset = QPoint(new_offset_x, new_offset_y)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._enable_roi_selection and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._is_selecting_roi = True
                self._roi_start = self.screen_to_image_coords(event.pos())
                self._roi_rect = QRect(self._roi_start, QSize(1, 1))
                self.update()
            else:
                self._is_panning = True
                self._last_mouse_pos = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._pan_offset += delta
            self._last_mouse_pos = event.pos()
            self.update()
        elif self._is_selecting_roi and self._roi_start:
            curr = self.screen_to_image_coords(event.pos())
            x1 = min(self._roi_start.x(), curr.x())
            y1 = min(self._roi_start.y(), curr.y())
            x2 = max(self._roi_start.x(), curr.x())
            y2 = max(self._roi_start.y(), curr.y())
            self._roi_rect = QRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.CrossCursor if self._enable_roi_selection else Qt.CursorShape.ArrowCursor)
        elif self._is_selecting_roi:
            self._is_selecting_roi = False
            if self._roi_rect and self._roi_rect.width() > 4 and self._roi_rect.height() > 4:
                self.roiChanged.emit(self._roi_rect)
            else:
                self._roi_rect = None
                self.update()


class ZoomableImageCanvas(QFrame):
    """
    Widget completo com barra de ferramentas embutida:
    Zoom (+, -, 100%, Ajustar), Indicador de %, Pan e suporte a ROI.
    """
    roiChanged = Signal(QRect)

    def __init__(self, parent: Optional[QWidget] = None, show_toolbar: bool = True):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #191B1E; border-radius: 6px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._view = _CanvasView(self)
        self._view.roiChanged.connect(self.roiChanged)
        layout.addWidget(self._view, stretch=1)

        if show_toolbar:
            tb = QHBoxLayout()
            tb.setContentsMargins(6, 2, 6, 2)
            tb.setSpacing(6)

            self._btn_zoom_out = QPushButton("-", self)
            self._btn_zoom_out.setFixedSize(26, 24)
            self._btn_zoom_out.setToolTip("Diminuir zoom")
            self._btn_zoom_out.clicked.connect(self._on_zoom_out)
            tb.addWidget(self._btn_zoom_out)

            self._lbl_zoom = QLabel("100%", self)
            self._lbl_zoom.setFixedWidth(46)
            self._lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lbl_zoom.setStyleSheet("font-size: 11px; color: #A0A5AD;")
            tb.addWidget(self._lbl_zoom)

            self._btn_zoom_in = QPushButton("+", self)
            self._btn_zoom_in.setFixedSize(26, 24)
            self._btn_zoom_in.setToolTip("Aumentar zoom")
            self._btn_zoom_in.clicked.connect(self._on_zoom_in)
            tb.addWidget(self._btn_zoom_in)

            self._btn_fit = QPushButton("Ajustar", self)
            self._btn_fit.setFixedHeight(24)
            self._btn_fit.setToolTip("Ajustar à tela")
            self._btn_fit.clicked.connect(self._on_fit)
            tb.addWidget(self._btn_fit)

            self._btn_100 = QPushButton("1:1", self)
            self._btn_100.setFixedSize(32, 24)
            self._btn_100.setToolTip("Tamanho original (100%)")
            self._btn_100.clicked.connect(self._on_100)
            tb.addWidget(self._btn_100)

            tb.addStretch()

            self._lbl_dims = QLabel("", self)
            self._lbl_dims.setStyleSheet("font-size: 11px; color: #80858D;")
            tb.addWidget(self._lbl_dims)

            layout.addLayout(tb)
        else:
            self._lbl_zoom = None
            self._lbl_dims = None

    def set_pixmap(self, pixmap: Optional[QPixmap], auto_fit: bool = True) -> None:
        self._view.set_pixmap(pixmap, auto_fit)
        self._update_labels()

    def set_image(self, pil_image) -> None:
        """Carrega diretamente uma imagem Pillow."""
        if pil_image is None:
            self.set_pixmap(None)
            return

        import io
        byte_arr = io.BytesIO()
        pil_image.save(byte_arr, format='PNG')
        pix = QPixmap()
        pix.loadFromData(byte_arr.getvalue())
        self.set_pixmap(pix)

    def _update_labels(self) -> None:
        if self._lbl_zoom:
            pct = int(self._view._zoom * 100)
            self._lbl_zoom.setText(f"{pct}%")
        if self._lbl_dims and self._view._pixmap and not self._view._pixmap.isNull():
            p = self._view._pixmap
            self._lbl_dims.setText(f"{p.width()} × {p.height()} px")
        elif self._lbl_dims:
            self._lbl_dims.setText("")

    def _on_zoom_in(self) -> None:
        self._view.zoom_in()
        self._update_labels()

    def _on_zoom_out(self) -> None:
        self._view.zoom_out()
        self._update_labels()

    def _on_fit(self) -> None:
        self._view.fit_to_view()
        self._update_labels()

    def _on_100(self) -> None:
        self._view.zoom_100()
        self._update_labels()

    def set_roi_selection_enabled(self, enabled: bool) -> None:
        self._view.set_roi_selection_enabled(enabled)

    def get_roi(self) -> Optional[QRect]:
        return self._view.get_roi()

    def set_roi(self, rect: Optional[QRect]) -> None:
        self._view.set_roi(rect)

    def clear_roi(self) -> None:
        self._view.clear_roi()

    def set_checkerboard_enabled(self, enabled: bool) -> None:
        self._view.set_checkerboard_enabled(enabled)

