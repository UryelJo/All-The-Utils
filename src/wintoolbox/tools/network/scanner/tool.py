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
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)
from .logic import (
    COMMON_PORTS,
    ArpDeviceItem,
    OpenPortItem,
    scan_arp_table,
    scan_ports_concurrent,
    scan_single_port,
)

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
        enable_sorting_on_table(self.table_ports)
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
        enable_sorting_on_table(self.table_arp)
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
            return scan_ports_concurrent(
                host=target,
                ports=ports,
                is_cancelled_fn=ctx.is_cancelled,
            )

        def on_done(open_ports: List[OpenPortItem]):
            self.btn_scan_ports.setEnabled(True)
            with batch_table_update(self.table_ports):
                self.table_ports.setRowCount(len(open_ports))
                for row, p in enumerate(open_ports):
                    self.table_ports.setItem(row, 0, SmartTableWidgetItem(str(p.port), sort_value=p.port, user_data=p))
                    self.table_ports.setItem(row, 1, SmartTableWidgetItem(p.service))
                    self.table_ports.setItem(row, 2, SmartTableWidgetItem(p.status))
            self.lbl_ports_status.setText(f"Varredura finalizada. {len(open_ports)} porta(s) aberta(s) encontrada(s).")

        self.runner.start_task(worker, on_finished=on_done)

    def _start_arp_scan(self):
        self.btn_scan_arp.setEnabled(False)
        self.lbl_arp_status.setText("Consultando tabela ARP e resolvendo nomes...")
        def worker(ctx):
            return scan_arp_table()

        def on_done(devices: List[ArpDeviceItem]):
            self.btn_scan_arp.setEnabled(True)
            with batch_table_update(self.table_arp):
                self.table_arp.setRowCount(len(devices))
                for row, d in enumerate(devices):
                    self.table_arp.setItem(row, 0, SmartTableWidgetItem(d.ip, user_data=d))
                    self.table_arp.setItem(row, 1, SmartTableWidgetItem(d.mac))
                    self.table_arp.setItem(row, 2, SmartTableWidgetItem(d.tipo))
                    self.table_arp.setItem(row, 3, SmartTableWidgetItem(d.hostname))
            self.lbl_arp_status.setText(f"Descoberta concluída: {len(devices)} dispositivo(s) localizado(s).")

        self.runner.start_task(worker, on_finished=on_done)
