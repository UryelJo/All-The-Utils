"""
Ferramenta: Gerenciador de DNS e Reset de Rede.
Troca rápida de DNS (Cloudflare, Google, Quad9, DHCP) e limpeza/reparo da pilha TCP/IP.
"""
import psutil
from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.shell import run_command, run_command_streaming
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from .logic import DNS_PRESETS, build_set_dns_command, get_active_interface_names

@register
class DnsManagerTool(Tool):
    id = "network.dns_manager"
    name = "Troca de DNS e Reset de Rede"
    category = "Rede e Internet"
    description = "Troca rápida de servidores DNS (Cloudflare, Google, Quad9) e restauração da pilha de rede (Flush DNS, Winsock)"
    keywords = ["dns", "cloudflare", "google", "quad9", "reset", "flushdns", "winsock", "ip", "rede", "reparo"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DnsManagerView(self, parent)

class DnsManagerView(QWidget):
    def __init__(self, tool: DnsManagerTool, parent: Optional[QWidget] = None):
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

        # Card 1: Troca Rápida de DNS
        card_dns = QFrame()
        card_dns.setProperty("class", "card")
        l_dns = QVBoxLayout(card_dns)
        l_dns.setContentsMargins(14, 12, 14, 12)
        l_dns.setSpacing(10)

        lbl_dns_hdr = QLabel("Configuração Rápida de DNS")
        lbl_dns_hdr.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_dns.addWidget(lbl_dns_hdr)

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Adaptador de Rede:"))
        self.cmb_ifaces = QComboBox()
        self.cmb_ifaces.addItems(get_active_interface_names())
        row_sel.addWidget(self.cmb_ifaces, stretch=1)
        l_dns.addLayout(row_sel)

        row_preset = QHBoxLayout()
        row_preset.addWidget(QLabel("Servidor DNS:"))
        self.cmb_presets = QComboBox()
        self.cmb_presets.addItems(list(DNS_PRESETS.keys()))
        row_preset.addWidget(self.cmb_presets, stretch=1)

        btn_apply_dns = QPushButton("Aplicar DNS")
        btn_apply_dns.setProperty("class", "primary")
        btn_apply_dns.clicked.connect(self._apply_dns)
        row_preset.addWidget(btn_apply_dns)
        l_dns.addLayout(row_preset)

        layout.addWidget(card_dns)

        # Card 2: Ferramentas de Reset e Limpeza de Rede
        card_reset = QFrame()
        card_reset.setProperty("class", "card")
        l_reset = QVBoxLayout(card_reset)
        l_reset.setContentsMargins(14, 12, 14, 12)
        l_reset.setSpacing(10)

        lbl_reset_hdr = QLabel("Diagnóstico e Reset da Pilha de Rede")
        lbl_reset_hdr.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_reset.addWidget(lbl_reset_hdr)

        grid = QGridLayout()
        grid.setSpacing(10)

        btn_flush = QPushButton("Limpar Cache DNS (ipconfig /flushdns)")
        btn_flush.clicked.connect(lambda: self._run_cmd("ipconfig /flushdns", "Limpeza de Cache DNS"))
        grid.addWidget(btn_flush, 0, 0)

        btn_renew = QPushButton("Renovar IP (release & renew)")
        btn_renew.clicked.connect(lambda: self._run_cmd("ipconfig /release && ipconfig /renew", "Renovação de IP"))
        grid.addWidget(btn_renew, 0, 1)

        btn_winsock = QPushButton("Restaurar Catálogo Winsock (netsh winsock reset)")
        btn_winsock.clicked.connect(lambda: self._run_cmd("netsh winsock reset", "Reset do Winsock", requires_admin=True))
        grid.addWidget(btn_winsock, 1, 0)

        btn_tcp = QPushButton("Restaurar Pilha TCP/IP (netsh int ip reset)")
        btn_tcp.clicked.connect(lambda: self._run_cmd("netsh int ip reset", "Reset TCP/IP", requires_admin=True))
        grid.addWidget(btn_tcp, 1, 1)

        l_reset.addLayout(grid)
        layout.addWidget(card_reset)

        # Painel de Log
        self.log_panel = LogPanelWidget()
        layout.addWidget(self.log_panel)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _apply_dns(self):
        if not is_admin():
            res = QMessageBox.question(
                self,
                "Privilégios de Administrador",
                "A alteração dos servidores DNS do Windows requer privilégios de Administrador.\n"
                "Deseja reiniciar a aplicação como Administrador agora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.Yes:
                request_elevation()
            return

        iface = self.cmb_ifaces.currentText()
        preset_key = self.cmb_presets.currentText()
        p1, p2 = DNS_PRESETS[preset_key]

        self.log_panel.append_log("INFO", f"Configurando DNS para o adaptador '{iface}'...")
        cmd = build_set_dns_command(iface, p1, p2)
        self._run_cmd(cmd, "Alteração de DNS")

    def _run_cmd(self, cmd_str: str, desc: str, requires_admin: bool = False):
        if requires_admin and not is_admin():
            res = QMessageBox.question(
                self,
                "Privilégios Necessários",
                f"A ação '{desc}' requer privilégios de Administrador.\n"
                "Deseja reiniciar a aplicação como Administrador agora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.Yes:
                request_elevation()
            return

        self.log_panel.append_log("INFO", f"Executando {desc}...")
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd_str, lambda l: ctx.on_log("INFO", l), shell=True),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )
