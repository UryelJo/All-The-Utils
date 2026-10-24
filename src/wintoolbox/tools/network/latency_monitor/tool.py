"""
Interface gráfica do Monitor Contínuo de Latência, Jitter e Perda de Pacotes.
"""
from typing import List, Optional
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.latency_monitor.logic import (
    calculate_stats, ping_host
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("network.latency_monitor.ui")


@register
class LatencyMonitorTool(Tool):
    id = "network.latency_monitor"
    name = "Monitor de Latência e Jitter de Rede"
    category = "Rede e Internet"
    description = "Monitoramento contínuo de ping, cálculo de jitter (RFC 3550) e taxa de perda de pacotes"
    keywords = ["ping", "latencia", "jitter", "lag", "perda de pacotes", "qualidade", "conexao", "estabilidade"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return LatencyMonitorView(self, parent)


class LatencyMonitorView(QWidget):
    def __init__(self, tool: LatencyMonitorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._samples: List[float] = []
        self._total_sent: int = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._ping_tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        # Barra de configuração
        config_bar = QHBoxLayout()
        config_bar.addWidget(QLabel("Servidor Alvo:"))

        self.combo_target = QComboBox()
        self.combo_target.addItems([
            "Cloudflare (1.1.1.1)",
            "Google DNS (8.8.8.8)",
            "OpenDNS (208.67.222.222)",
            "Outro (Personalizado)"
        ])
        self.combo_target.currentIndexChanged.connect(self._on_target_changed)
        config_bar.addWidget(self.combo_target)

        self.txt_custom_host = QLineEdit()
        self.txt_custom_host.setPlaceholderText("Ex: google.com ou 192.168.1.1")
        self.txt_custom_host.setVisible(False)
        config_bar.addWidget(self.txt_custom_host)

        config_bar.addWidget(QLabel("Intervalo:"))
        self.combo_interval = QComboBox()
        self.combo_interval.addItem("1 segundo", 1000)
        self.combo_interval.addItem("2 segundos", 2000)
        self.combo_interval.addItem("5 segundos", 5000)
        config_bar.addWidget(self.combo_interval)

        self.btn_toggle = QPushButton("Iniciar Monitoramento")
        self.btn_toggle.setProperty("accent", True)
        self.btn_toggle.clicked.connect(self._toggle_monitoring)
        config_bar.addWidget(self.btn_toggle)

        config_bar.addStretch()
        layout.addLayout(config_bar)

        # Painel de métricas principais em destaque
        metrics_card = QFrame()
        metrics_card.setObjectName("Card")
        m_lay = QGridLayout(metrics_card)
        m_lay.setContentsMargins(16, 16, 16, 16)
        m_lay.setSpacing(12)

        self.val_current = QLabel("0 ms")
        self.val_current.setStyleSheet("font-size: 22px; font-weight: bold; color: #0078d4;")
        self.val_avg = QLabel("0 ms")
        self.val_avg.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.val_min = QLabel("0 ms")
        self.val_max = QLabel("0 ms")
        self.val_jitter = QLabel("0 ms")
        self.val_jitter.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.val_loss = QLabel("0.0%")
        self.val_loss.setStyleSheet("font-size: 18px; font-weight: bold;")

        m_lay.addWidget(QLabel("Latência Atual:"), 0, 0)
        m_lay.addWidget(self.val_current, 1, 0)

        m_lay.addWidget(QLabel("Média:"), 0, 1)
        m_lay.addWidget(self.val_avg, 1, 1)

        m_lay.addWidget(QLabel("Mín / Máx:"), 0, 2)
        min_max_box = QHBoxLayout()
        min_max_box.addWidget(self.val_min)
        min_max_box.addWidget(QLabel("/"))
        min_max_box.addWidget(self.val_max)
        m_lay.addLayout(min_max_box, 1, 2)

        m_lay.addWidget(QLabel("Jitter (Variação):"), 0, 3)
        m_lay.addWidget(self.val_jitter, 1, 3)

        m_lay.addWidget(QLabel("Perda de Pacotes:"), 0, 4)
        m_lay.addWidget(self.val_loss, 1, 4)

        layout.addWidget(metrics_card)

        # Histórico recente em tabela
        layout.addWidget(QLabel("Histórico das Últimas Amostras de Latência:"))
        self.table_history = QTableWidget(0, 3)
        self.table_history.setHorizontalHeaderLabels(["Nº", "Tempo de Resposta", "Status"])
        self.table_history.setColumnWidth(0, 80)
        self.table_history.setColumnWidth(1, 160)
        self.table_history.setColumnWidth(2, 200)
        layout.addWidget(self.table_history, stretch=1)

    def _on_target_changed(self, idx: int) -> None:
        self.txt_custom_host.setVisible(idx == 3)

    def _get_target_host(self) -> str:
        idx = self.combo_target.currentIndex()
        if idx == 0:
            return "1.1.1.1"
        elif idx == 1:
            return "8.8.8.8"
        elif idx == 2:
            return "208.67.222.222"
        return self.txt_custom_host.text().strip() or "8.8.8.8"

    def _toggle_monitoring(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.btn_toggle.setText("Iniciar Monitoramento")
            self.combo_target.setEnabled(True)
            self.combo_interval.setEnabled(True)
        else:
            self._samples.clear()
            self._total_sent = 0
            self.table_history.setRowCount(0)
            interval_ms = self.combo_interval.currentData()
            self._timer.start(interval_ms)
            self.btn_toggle.setText("Parar Monitoramento")
            self.combo_target.setEnabled(False)
            self.combo_interval.setEnabled(False)
            self._ping_tick()

    def _ping_tick(self) -> None:
        target = self._get_target_host()
        self._total_sent += 1

        def _worker():
            return ping_host(target, timeout_ms=1000)

        def _on_done(result):
            success, ms = result
            if success:
                self._samples.append(ms)

            # Atualiza métricas
            stats = calculate_stats(self._samples, self._total_sent)
            self.val_current.setText(f"{stats['current']} ms" if success else "Tempo esgotado")
            self.val_current.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {'#107c41' if success else '#d83b01'};")

            self.val_avg.setText(f"{stats['avg']} ms")
            self.val_min.setText(f"{stats['min']} ms")
            self.val_max.setText(f"{stats['max']} ms")
            self.val_jitter.setText(f"{stats['jitter']} ms")
            self.val_loss.setText(f"{stats['packet_loss_pct']}%")

            # Atualiza tabela
            row = self.table_history.rowCount()
            self.table_history.insertRow(0)
            self.table_history.setItem(0, 0, QTableWidgetItem(f"#{self._total_sent}"))
            self.table_history.setItem(0, 1, QTableWidgetItem(f"{ms:.1f} ms" if success else "Falha"))

            st_item = QTableWidgetItem("Sucesso" if success else "Tempo Esgotado")
            st_item.setForeground(Qt.green if success else Qt.red)
            self.table_history.setItem(0, 2, st_item)

            if self.table_history.rowCount() > 100:
                self.table_history.removeRow(100)

        TaskRunner.run(_worker, on_success=_on_done)
