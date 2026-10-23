"""
Ferramenta: Scanner de Rede (Portas e Dispositivos Locais ARP).
"""
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 135: "RPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Proxy"
}

def scan_single_port(host: str, port: int, timeout: float = 0.5) -> Optional[Dict]:
    """Testa se uma porta TCP está aberta."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        if res == 0:
            service = COMMON_PORTS.get(port, "Desconhecido")
            return {"port": port, "service": service, "status": "Aberta"}
    except Exception:
        pass
    return None

def scan_arp_table() -> List[Dict[str, str]]:
    """Lê a tabela ARP do Windows para listar dispositivos ativos na rede local."""
    devices = []
    try:
        out = subprocess.check_output("arp -a", shell=True, text=True, errors="replace")
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].count('.') == 3:
                ip = parts[0]
                mac = parts[1].replace('-', ':').upper()
                tipo = parts[2]
                if mac != "FF:FF:FF:FF:FF:FF" and not ip.startswith("224.") and not ip.startswith("239."):
                    # Tenta resolver o hostname (DNS reverso)
                    hostname = "-"
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        pass
                    devices.append({
                        "ip": ip,
                        "mac": mac,
                        "tipo": tipo,
                        "hostname": hostname
                    })
    except Exception:
        pass
    return devices

@register
class ScannerTool(Tool):
    id = "network.scanner"
    name = "Scanner de Portas e Dispositivos"
    category = "Rede e Internet"
    description = "Varredura de portas abertas (TCP) e descoberta de dispositivos na rede local (ARP)"
    keywords = ["scanner", "portas", "arp", "dispositivos", "rede", "tcp", "aberta", "segurança"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ScannerView(self, parent)

class ScannerView(QWidget):
    def __init__(self, tool: ScannerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._build_ui()

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

        tabs = QTabWidget()

        # ABA 1: Scanner de Portas
        tab_ports = QWidget()
        l_ports = QVBoxLayout(tab_ports)
        l_ports.setSpacing(10)

        row_ctrl = QHBoxLayout()
        row_ctrl.addWidget(QLabel("Alvo (IP/Host):"))
        self.txt_port_target = QLineEdit("127.0.0.1")
        self.txt_port_target.setFixedWidth(140)
        row_ctrl.addWidget(self.txt_port_target)

        row_ctrl.addWidget(QLabel("Modo:"))
        self.cmb_port_mode = QComboBox()
        self.cmb_port_mode.addItems(["Portas Comuns Principais (21-8080)", "Faixa Customizada (1-1024)"])
        row_ctrl.addWidget(self.cmb_port_mode)

        self.btn_scan_ports = QPushButton("Iniciar Varredura")
        self.btn_scan_ports.setProperty("class", "primary")
        self.btn_scan_ports.clicked.connect(self._start_port_scan)
        row_ctrl.addWidget(self.btn_scan_ports)
        row_ctrl.addStretch()
        l_ports.addLayout(row_ctrl)

        self.table_ports = QTableWidget(0, 3)
        self.table_ports.setHorizontalHeaderLabels(["Porta", "Serviço Padrão", "Status"])
        self.table_ports.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_ports.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_ports.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_ports.verticalHeader().setVisible(False)
        self.table_ports.setFixedHeight(240)
        l_ports.addWidget(self.table_ports)

        self.lbl_ports_status = QLabel("Pronto para escanear.")
        self.lbl_ports_status.setProperty("class", "secondary")
        l_ports.addWidget(self.lbl_ports_status)

        tabs.addTab(tab_ports, "Scanner de Portas TCP")

        # ABA 2: Dispositivos na Rede Local
        tab_arp = QWidget()
        l_arp = QVBoxLayout(tab_arp)
        l_arp.setSpacing(10)

        row_arp = QHBoxLayout()
        self.btn_scan_arp = QPushButton("Localizar Dispositivos (ARP)")
        self.btn_scan_arp.setProperty("class", "primary")
        self.btn_scan_arp.clicked.connect(self._start_arp_scan)
        row_arp.addWidget(self.btn_scan_arp)
        row_arp.addStretch()
        l_arp.addLayout(row_arp)

        self.table_arp = QTableWidget(0, 4)
        self.table_arp.setHorizontalHeaderLabels(["Endereço IP", "Endereço Físico (MAC)", "Tipo", "Nome do Dispositivo"])
        self.table_arp.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_arp.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_arp.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_arp.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_arp.verticalHeader().setVisible(False)
        self.table_arp.setFixedHeight(240)
        l_arp.addWidget(self.table_arp)

        self.lbl_arp_status = QLabel("Clique no botão para listar dispositivos conectados à mesma rede.")
        self.lbl_arp_status.setProperty("class", "secondary")
        l_arp.addWidget(self.lbl_arp_status)

        tabs.addTab(tab_arp, "Dispositivos na Rede Local (ARP)")

        layout.addWidget(tabs)
        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _start_port_scan(self):
        target = self.txt_port_target.text().strip() or "127.0.0.1"
        mode_idx = self.cmb_port_mode.currentIndex()
        ports = list(COMMON_PORTS.keys()) if mode_idx == 0 else list(range(1, 1025))

        self.table_ports.setRowCount(0)
        self.btn_scan_ports.setEnabled(False)
        self.lbl_ports_status.setText(f"Escaneando {len(ports)} portas em {target}...")

        def worker(ctx):
            open_ports = []
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = {executor.submit(scan_single_port, target, p): p for p in ports}
                for f in as_completed(futures):
                    if ctx.is_cancelled():
                        break
                    res = f.result()
                    if res:
                        open_ports.append(res)
            return open_ports

        def on_done(res):
            self.btn_scan_ports.setEnabled(True)
            open_ports = sorted(res, key=lambda x: x["port"])
            self.table_ports.setRowCount(len(open_ports))
            for row, p in enumerate(open_ports):
                self.table_ports.setItem(row, 0, QTableWidgetItem(str(p["port"])))
                self.table_ports.setItem(row, 1, QTableWidgetItem(p["service"]))
                self.table_ports.setItem(row, 2, QTableWidgetItem(p["status"]))
            self.lbl_ports_status.setText(f"Varredura finalizada. {len(open_ports)} porta(s) aberta(s) encontrada(s).")

        w = self.runner.start_task(worker, on_finished=on_done)

    def _start_arp_scan(self):
        self.btn_scan_arp.setEnabled(False)
        self.lbl_arp_status.setText("Consultando tabela ARP e resolvendo nomes...")
        def worker(ctx):
            return scan_arp_table()

        def on_done(devices):
            self.btn_scan_arp.setEnabled(True)
            self.table_arp.setRowCount(len(devices))
            for row, d in enumerate(devices):
                self.table_arp.setItem(row, 0, QTableWidgetItem(d["ip"]))
                self.table_arp.setItem(row, 1, QTableWidgetItem(d["mac"]))
                self.table_arp.setItem(row, 2, QTableWidgetItem(d["tipo"]))
                self.table_arp.setItem(row, 3, QTableWidgetItem(d["hostname"]))
            self.lbl_arp_status.setText(f"Descoberta concluída: {len(devices)} dispositivo(s) localizado(s).")

        self.runner.start_task(worker, on_finished=on_done)
