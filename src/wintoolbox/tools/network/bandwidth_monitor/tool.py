"""
Ferramenta: Monitor de Largura de Banda em Tempo Real.
Exibe velocidade de download/upload, tráfego acumulado e gráfico dos últimos 60 segundos.
"""
from collections import deque
from typing import Deque, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.network.bandwidth_monitor.logic import (
    BandwidthRate,
    NetworkSnapshot,
    calculate_bandwidth_rate,
    format_bandwidth_speed,
    format_total_bytes,
    get_available_interfaces,
    take_network_snapshot,
)


class BandwidthGraphWidget(QWidget):
    """Widget de exibição de gráfico em linha temporal dos últimos 60 segundos."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(180)
        self.download_history: Deque[float] = deque([0.0] * 60, maxlen=60)
        self.upload_history: Deque[float] = deque([0.0] * 60, maxlen=60)

    def add_sample(self, down_bps: float, up_bps: float) -> None:
        self.download_history.append(down_bps)
        self.upload_history.append(up_bps)
        self.update()

    def clear_samples(self) -> None:
        self.download_history = deque([0.0] * 60, maxlen=60)
        self.upload_history = deque([0.0] * 60, maxlen=60)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Fundo escuro elegante
        painter.fillRect(0, 0, w, h, QColor(15, 23, 42))

        # Grade sutil
        painter.setPen(QPen(QColor(51, 65, 85, 120), 1, Qt.DashLine))
        for y_step in (h * 0.25, h * 0.5, h * 0.75):
            painter.drawLine(0, int(y_step), w, int(y_step))

        max_val = max(max(self.download_history), max(self.upload_history), 1024 * 10.0)  # mínimo 10 KB/s escala

        def _draw_series(history: Deque[float], color: QColor) -> None:
            path = QPainterPath()
            points_count = len(history)
            x_step = w / max(1, points_count - 1)

            for i, val in enumerate(history):
                x = i * x_step
                norm = min(1.0, val / max_val)
                y = h - (norm * (h - 20)) - 10
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            painter.setPen(QPen(color, 2))
            painter.drawPath(path)

        # Download (Azul Cyan) e Upload (Verde Esmeralda)
        _draw_series(self.download_history, QColor(6, 182, 212))
        _draw_series(self.upload_history, QColor(34, 197, 94))

        # Legenda no canto superior esquerdo
        painter.setPen(QColor(6, 182, 212))
        painter.drawText(12, 20, "• Download")
        painter.setPen(QColor(34, 197, 94))
        painter.drawText(90, 20, "• Upload")

        # Escala máxima no canto superior direito
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(w - 110, 20, f"Pico: {format_bandwidth_speed(max_val)}")


@register
class BandwidthMonitorTool(Tool):
    id = "network.bandwidth_monitor"
    name = "Monitor de Tráfego de Rede"
    category = "Rede"
    description = "Monitore em tempo real as velocidades de download e upload por interface com gráfico de linha"
    keywords = ["rede", "trafego", "largura de banda", "download", "upload", "bandwidth", "velocidade", "grafico"]

    def __init__(self) -> None:
        super().__init__()
        self._prev_snapshot: Optional[NetworkSnapshot] = None
        self._initial_snapshot: Optional[NetworkSnapshot] = None
        self._is_paused: bool = False

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Barra Superior de Controles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        top_bar.addWidget(QLabel("Interface de Rede:"))
        self.cmb_iface = QComboBox()
        self.cmb_iface.addItem("Todas as Interfaces")
        for iface in get_available_interfaces():
            self.cmb_iface.addItem(iface)
        self.cmb_iface.currentTextChanged.connect(self._on_interface_changed)
        top_bar.addWidget(self.cmb_iface, stretch=1)

        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.clicked.connect(self._toggle_pause)
        top_bar.addWidget(self.btn_pause)

        self.btn_reset = QPushButton("Zerar Totais")
        self.btn_reset.clicked.connect(self._reset_counters)
        top_bar.addWidget(self.btn_reset)

        main_layout.addLayout(top_bar)

        # Cards Grandes de Métricas
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        # Card Download
        card_down = QFrame()
        card_down.setStyleSheet(
            "background-color: #f0fdfa; border: 1px solid #99f6e4; border-radius: 8px; padding: 14px;"
        )
        cd_layout = QVBoxLayout(card_down)
        cd_layout.addWidget(QLabel("DOWNLOAD ATUAL"))
        self.lbl_down_speed = QLabel("0.0 B/s")
        self.lbl_down_speed.setStyleSheet("font-size: 26px; font-weight: 700; color: #0f766e;")
        cd_layout.addWidget(self.lbl_down_speed)
        self.lbl_down_total = QLabel("Total na Sessão: 0 B")
        self.lbl_down_total.setStyleSheet("color: #115e59; font-size: 12px;")
        cd_layout.addWidget(self.lbl_down_total)
        cards_layout.addWidget(card_down)

        # Card Upload
        card_up = QFrame()
        card_up.setStyleSheet(
            "background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px;"
        )
        cu_layout = QVBoxLayout(card_up)
        cu_layout.addWidget(QLabel("UPLOAD ATUAL"))
        self.lbl_up_speed = QLabel("0.0 B/s")
        self.lbl_up_speed.setStyleSheet("font-size: 26px; font-weight: 700; color: #15803d;")
        cu_layout.addWidget(self.lbl_up_speed)
        self.lbl_up_total = QLabel("Total na Sessão: 0 B")
        self.lbl_up_total.setStyleSheet("color: #166534; font-size: 12px;")
        cu_layout.addWidget(self.lbl_up_total)
        cards_layout.addWidget(card_up)

        main_layout.addLayout(cards_layout)

        # Gráfico Histórico
        self.graph = BandwidthGraphWidget(container)
        main_layout.addWidget(self.graph)

        main_layout.addStretch()

        self._reset_counters()
        container.destroyed.connect(self._timer.stop)
        self._timer.start()
        return container

    def _on_interface_changed(self) -> None:
        self._reset_counters()

    def _reset_counters(self) -> None:
        try:
            iface = self._current_iface()
            snap = take_network_snapshot(iface)
            self._prev_snapshot = snap
            self._initial_snapshot = snap
            if hasattr(self, "graph"):
                self.graph.clear_samples()
            if hasattr(self, "lbl_down_speed"):
                self.lbl_down_speed.setText("0.0 B/s")
                self.lbl_up_speed.setText("0.0 B/s")
                self.lbl_down_total.setText("Total na Sessão: 0 B")
                self.lbl_up_total.setText("Total na Sessão: 0 B")
        except RuntimeError:
            self._timer.stop()

    def _current_iface(self) -> Optional[str]:
        t = self.cmb_iface.currentText()
        return None if "Todas" in t else t

    def _toggle_pause(self) -> None:
        self._is_paused = not self._is_paused
        self.btn_pause.setText("Retomar" if self._is_paused else "Pausar")

    def _on_tick(self) -> None:
        if self._is_paused:
            return

        try:
            if not hasattr(self, "cmb_iface"):
                self._timer.stop()
                return
            iface = self._current_iface()
        except RuntimeError:
            self._timer.stop()
            return

        curr_snap = take_network_snapshot(iface)

        try:
            if self._prev_snapshot is not None:
                rate = calculate_bandwidth_rate(self._prev_snapshot, curr_snap)
                self.lbl_down_speed.setText(rate.download_display)
                self.lbl_up_speed.setText(rate.upload_display)
                self.graph.add_sample(rate.download_bytes_per_sec, rate.upload_bytes_per_sec)

            if self._initial_snapshot is not None:
                total_recv = max(0, curr_snap.bytes_recv - self._initial_snapshot.bytes_recv)
                total_sent = max(0, curr_snap.bytes_sent - self._initial_snapshot.bytes_sent)
                self.lbl_down_total.setText(f"Total na Sessão: {format_total_bytes(total_recv)}")
                self.lbl_up_total.setText(f"Total na Sessão: {format_total_bytes(total_sent)}")

            self._prev_snapshot = curr_snap
        except RuntimeError:
            self._timer.stop()
