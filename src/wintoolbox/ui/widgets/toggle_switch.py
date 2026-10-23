"""
Componente Interruptor Deslizante (ToggleSwitch) estilo Windows 11 Fluent Design.
Herda de QCheckBox para compatibilidade transparente com sinais (.toggled, .isChecked, .setChecked).
"""
from typing import Optional
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QCheckBox, QWidget

from wintoolbox.ui.theme import get_current_tokens


class ToggleSwitch(QCheckBox):
    """Interruptor visual estilo Windows 11 com animação suave."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._thumb_pos: float = 0.0
        self._track_width = 40
        self._track_height = 20

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.toggled.connect(self._animate_thumb)

    def get_thumb_position(self) -> float:
        return self._thumb_pos

    def set_thumb_position(self, pos: float) -> None:
        self._thumb_pos = pos
        self.update()

    thumb_position = Property(float, get_thumb_position, set_thumb_position)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._thumb_pos = 1.0 if checked else 0.0
        self.update()

    def _animate_thumb(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        txt = self.text()
        if not txt:
            return QSize(self._track_width + 4, self._track_height + 4)
        fm = self.fontMetrics()
        w = self._track_width + 10 + fm.horizontalAdvance(txt) + 8
        h = max(self._track_height + 4, fm.height() + 4)
        return QSize(w, h)

    def hitButton(self, pos) -> bool:
        return self.contentsRect().contains(pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.hitButton(event.position().toPoint()):
            self.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        t = get_current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        y_offset = (self.height() - self._track_height) / 2.0
        track_rect = QRectF(1.0, y_offset, float(self._track_width), float(self._track_height))
        radius = self._track_height / 2.0

        # Cor da trilha e borda
        if not self.isEnabled():
            track_bg = QColor(t.bg_input)
            border_col = QColor(t.border_color)
            thumb_col = QColor(t.text_muted)
        elif self.isChecked():
            track_bg = QColor(t.accent)
            border_col = QColor(t.accent)
            thumb_col = QColor("#ffffff")
        else:
            track_bg = QColor(t.bg_input)
            border_col = QColor(t.text_muted)
            thumb_col = QColor(t.text_secondary)

        painter.setPen(QPen(border_col, 1.2))
        painter.setBrush(track_bg)
        painter.drawRoundedRect(track_rect, radius, radius)

        # Círculo interno (thumb)
        margin = 3.5
        thumb_diameter = self._track_height - (margin * 2.0)
        travel = self._track_width - thumb_diameter - (margin * 2.0)
        thumb_x = 1.0 + margin + (self._thumb_pos * travel)
        thumb_y = y_offset + margin

        painter.setPen(Qt.NoPen)
        painter.setBrush(thumb_col)
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter))

        # Texto opcional ao lado direito
        txt = self.text()
        if txt:
            text_x = self._track_width + 12
            text_rect = QRectF(text_x, 0, self.width() - text_x, self.height())
            painter.setPen(QColor(t.text_primary if self.isEnabled() else t.text_muted))
            f = self.font()
            if f.pointSize() <= 0:
                f.setPointSize(10)
            painter.setFont(f)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, txt)

        painter.end()
