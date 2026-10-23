"""
Ferramenta: Informações de IP e Monitor de Rede em Tempo Real.
"""
import time
import socket
import urllib.request
import json
import psutil
from typing import Dict, List, Optional
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from .logic import (
    NetworkInterfaceInfo,
    TrafficRateInfo,
    calculate_traffic_rate,
    fetch_public_ip,
    get_local_interfaces,
)

@register
class IpInfoTool(Tool):
    id = "network.ip_info"
    name = "Informações de IP e Monitor de Rede"
    category = "Rede e Internet"
    description = "Consulta de IP local e público, adaptadores de rede e velocidade de tráfego em tempo real"
    keywords = ["ip", "rede", "conexao", "publico", "local", "mac", "interface", "velocidade", "download", "upload"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return IpInfoView(self, parent)

class IpInfoView(QWidget):
    def __init__(self, tool: IpInfoTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._last_net_bytes = psutil.net_io_counters()
        self._last_time = time.time()

        self._build_ui()
        self._refresh_static_data()

        # Timer para velocidade em tempo real (1 segundo)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_traffic)
        self.timer.start(1000)

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

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

        # Cartão 1: IP Público e Tráfego Atual
        row_top = QHBoxLayout()
        row_top.setSpacing(12)

        # Card IP Público
        card_pub = QFrame()
        card_pub.setProperty("class", "card")
        l_pub = QVBoxLayout(card_pub)
        l_pub.setContentsMargins(14, 12, 14, 12)
        l_pub.addWidget(QLabel("Endereço IP Público (Internet)"))

        self.lbl_pub_ip = QLabel("Consultando...")
        self.lbl_pub_ip.setStyleSheet("font-size: 18px; font-weight: 700; color: #0078d4;")
        l_pub.addWidget(self.lbl_pub_ip)

        btn_refresh_pub = QPushButton("Atualizar IP Público")
        btn_refresh_pub.clicked.connect(self._refresh_public_ip)
        l_pub.addWidget(btn_refresh_pub)
        row_top.addWidget(card_pub, stretch=1)

        # Card Tráfego em Tempo Real
        card_traffic = QFrame()
        card_traffic.setProperty("class", "card")
        l_traf = QVBoxLayout(card_traffic)
        l_traf.setContentsMargins(14, 12, 14, 12)
        l_traf.addWidget(QLabel("Velocidade Atual de Tráfego"))

        self.lbl_down = QLabel("Download: 0.0 KB/s")
        self.lbl_down.setStyleSheet("font-size: 14px; font-weight: 600; color: #10b981;")
        l_traf.addWidget(self.lbl_down)

        self.lbl_up = QLabel("Upload: 0.0 KB/s")
        self.lbl_up.setStyleSheet("font-size: 14px; font-weight: 600; color: #3b82f6;")
        l_traf.addWidget(self.lbl_up)

        row_top.addWidget(card_traffic, stretch=1)
        layout.addLayout(row_top)

        # Cartão 2: Adaptadores Locais
        card_ifaces = QFrame()
        card_ifaces.setProperty("class", "card")
        l_ifaces = QVBoxLayout(card_ifaces)
        l_ifaces.setContentsMargins(14, 12, 14, 12)
        l_ifaces.addWidget(QLabel("Adaptadores de Rede Locais"))

        self.table_ifaces = QTableWidget(0, 5)
        self.table_ifaces.setHorizontalHeaderLabels([
            "Adaptador", "Status", "IPv4 Local", "Endereço MAC", "IPv6"
        ])
        self.table_ifaces.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_ifaces.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_ifaces.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_ifaces.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_ifaces.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_ifaces.verticalHeader().setVisible(False)
        self.table_ifaces.setFixedHeight(180)
        l_ifaces.addWidget(self.table_ifaces)

        layout.addWidget(card_ifaces)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _refresh_static_data(self):
        ifaces = get_local_interfaces()
        self.table_ifaces.setRowCount(len(ifaces))
        for row, item in enumerate(ifaces):
            self.table_ifaces.setItem(row, 0, QTableWidgetItem(item.name))
            self.table_ifaces.setItem(row, 1, QTableWidgetItem(item.status))
            self.table_ifaces.setItem(row, 2, QTableWidgetItem(item.ipv4))
            self.table_ifaces.setItem(row, 3, QTableWidgetItem(item.mac))
            self.table_ifaces.setItem(row, 4, QTableWidgetItem(item.ipv6))

        self._refresh_public_ip()

    def _refresh_public_ip(self):
        self.lbl_pub_ip.setText("Consultando...")
        from wintoolbox.core.tasks import run_task

        def worker(ctx):
            return fetch_public_ip()["ip"]

        # O TaskWorker solto numa variável local era coletado antes de entregar o resultado:
        # o rótulo ficava em "Consultando..." para sempre
        run_task(worker, on_done=lambda ip, exc: self.lbl_pub_ip.setText(
            str(ip) if exc is None else "Indisponível (sem conexão?)"))

    def _update_traffic(self):
        try:
            now = time.time()
            elapsed = now - self._last_time
            if elapsed <= 0:
                return

            curr = psutil.net_io_counters()
            rates = calculate_traffic_rate(self._last_net_bytes, curr, elapsed)
            self._last_net_bytes = curr
            self._last_time = now

            self.lbl_down.setText(f"Download: {rates.down_str}")
            self.lbl_up.setText(f"Upload: {rates.up_str}")
        except Exception:
            pass

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.timer.start(1000)
        self._refresh_static_data()
        super().showEvent(event)
