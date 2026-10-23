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

def get_local_interfaces() -> List[Dict[str, str]]:
    """Coleta adaptadores de rede, endereços IP e MAC locais."""
    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface_name, addr_list in addrs.items():
        is_up = stats[iface_name].isup if iface_name in stats else False
        ipv4 = "-"
        ipv6 = "-"
        mac = "-"
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ipv4 = addr.address
            elif addr.family == socket.AF_INET6:
                ipv6 = addr.address.split('%')[0]
            elif addr.family == psutil.AF_LINK:
                mac = addr.address

        if ipv4 != "-" or mac != "-":
            interfaces.append({
                "name": iface_name,
                "status": "Conectado" if is_up else "Desconectado",
                "ipv4": ipv4,
                "ipv6": ipv6,
                "mac": mac.upper()
            })
    return interfaces

def fetch_public_ip() -> Dict[str, str]:
    """Consulta o endereço IP público e detalhes básicos de rede externa."""
    urls = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/all.json"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ip = data.get("ip") or data.get("ip_addr", "Desconhecido")
                return {"ip": ip, "origem": url}
        except Exception:
            continue
    return {"ip": "Indisponível (Sem conexão externa)", "origem": ""}

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
            self.table_ifaces.setItem(row, 0, QTableWidgetItem(item["name"]))
            self.table_ifaces.setItem(row, 1, QTableWidgetItem(item["status"]))
            self.table_ifaces.setItem(row, 2, QTableWidgetItem(item["ipv4"]))
            self.table_ifaces.setItem(row, 3, QTableWidgetItem(item["mac"]))
            self.table_ifaces.setItem(row, 4, QTableWidgetItem(item["ipv6"]))

        self._refresh_public_ip()

    def _refresh_public_ip(self):
        self.lbl_pub_ip.setText("Consultando...")
        from PySide6.QtCore import QThreadPool
        from wintoolbox.core.tasks import TaskWorker
        def worker(ctx):
            info = fetch_public_ip()
            return info["ip"]
        w = TaskWorker(worker)
        w.signals.finished.connect(lambda ip: self.lbl_pub_ip.setText(str(ip)))
        QThreadPool.globalInstance().start(w)

    def _update_traffic(self):
        try:
            now = time.time()
            elapsed = now - self._last_time
            if elapsed <= 0:
                return

            curr = psutil.net_io_counters()
            bytes_recv = curr.bytes_recv - self._last_net_bytes.bytes_recv
            bytes_sent = curr.bytes_sent - self._last_net_bytes.bytes_sent

            self._last_net_bytes = curr
            self._last_time = now

            down_kb = (bytes_recv / elapsed) / 1024
            up_kb = (bytes_sent / elapsed) / 1024

            down_str = f"{down_kb/1024:.2f} MB/s" if down_kb >= 1024 else f"{down_kb:.1f} KB/s"
            up_str = f"{up_kb/1024:.2f} MB/s" if up_kb >= 1024 else f"{up_kb:.1f} KB/s"

            self.lbl_down.setText(f"Download: {down_str}")
            self.lbl_up.setText(f"Upload: {up_str}")
        except Exception:
            pass

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.timer.start(1000)
        self._refresh_static_data()
        super().showEvent(event)
