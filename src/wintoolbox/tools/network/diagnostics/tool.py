"""
Ferramenta: Diagnóstico de Rede e Domínios.
Ping, Traceroute, DNS Lookup, Whois, Verificador de Site Online e Certificados SSL.
"""
import ssl
import socket
import datetime
import urllib.request
import time
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.shell import run_command_streaming
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from .logic import (
    is_safe_host,
    SiteCheckResult,
    SslInspectionResult,
    check_site_availability,
    inspect_ssl_certificate,
    perform_whois_query,
)

@register
class DiagnosticsTool(Tool):
    id = "network.diagnostics"
    name = "Diagnóstico de Rede e Domínios"
    category = "Rede e Internet"
    description = "Ping, Traceroute, Nslookup, Whois, Verificador de Site Online e Certificado SSL"
    keywords = ["ping", "traceroute", "tracert", "nslookup", "whois", "ssl", "status", "site", "dominio", "latencia"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DiagnosticsView(self, parent)

class DiagnosticsView(QWidget):
    def __init__(self, tool: DiagnosticsTool, parent: Optional[QWidget] = None):
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

        # Card de Controle de Entrada
        card_input = QFrame()
        card_input.setProperty("class", "card")
        l_in = QVBoxLayout(card_input)
        l_in.setContentsMargins(14, 12, 14, 12)
        l_in.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.setSpacing(8)

        lbl_target = QLabel("Destino / Domínio / IP:")
        row_in.addWidget(lbl_target)

        self.txt_host = QLineEdit("google.com")
        self.txt_host.setPlaceholderText("Ex: 1.1.1.1 ou github.com")
        row_in.addWidget(self.txt_host, stretch=1)
        l_in.addLayout(row_in)

        # Ações de Diagnóstico em Botões
        row_btns = QHBoxLayout()
        row_btns.setSpacing(8)

        btn_ping = QPushButton("Executar Ping")
        btn_ping.clicked.connect(self._run_ping)
        row_btns.addWidget(btn_ping)

        btn_tracert = QPushButton("Traceroute")
        btn_tracert.clicked.connect(self._run_tracert)
        row_btns.addWidget(btn_tracert)

        btn_dns = QPushButton("DNS (Nslookup)")
        btn_dns.clicked.connect(self._run_dns)
        row_btns.addWidget(btn_dns)

        btn_whois = QPushButton("WHOIS")
        btn_whois.clicked.connect(self._run_whois)
        row_btns.addWidget(btn_whois)

        btn_ssl = QPushButton("Ver Certificado SSL")
        btn_ssl.clicked.connect(self._run_ssl)
        row_btns.addWidget(btn_ssl)

        btn_site = QPushButton("Verificar Site Online")
        btn_site.clicked.connect(self._run_site_check)
        row_btns.addWidget(btn_site)

        l_in.addLayout(row_btns)
        layout.addWidget(card_input)

        # Painel de Log / Saída
        self.log_panel = LogPanelWidget()
        layout.addWidget(self.log_panel)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _get_target(self) -> str:
        return self.txt_host.text().strip() or "google.com"

    def _get_command_target(self) -> Optional[str]:
        """Alvo validado para ping/tracert/nslookup: só hostname/IP, nunca opções ou metacaracteres."""
        target = self._get_target()
        if not is_safe_host(target):
            self.log_panel.append_log("ERROR", f"Host inválido: {target!r}. Use apenas um domínio ou endereço IP.")
            return None
        return target

    def _run_ping(self):
        target = self._get_command_target()
        if not target:
            return
        self.log_panel.append_log("INFO", f"Iniciando Ping para {target}...")
        cmd = ["ping", "-n", "4", target]
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd, lambda line: ctx.on_log("INFO", line)),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_tracert(self):
        target = self._get_command_target()
        if not target:
            return
        self.log_panel.append_log("INFO", f"Iniciando Traceroute para {target} (aguarde os saltos)...")
        cmd = ["tracert", "-d", "-h", "15", target]
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd, lambda line: ctx.on_log("INFO", line)),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_dns(self):
        target = self._get_command_target()
        if not target:
            return
        self.log_panel.append_log("INFO", f"Consultando registros DNS para {target}...")
        cmd = ["nslookup", target]
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd, lambda line: ctx.on_log("INFO", line)),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_whois(self):
        target = self._get_target()
        self.log_panel.append_log("INFO", f"Consultando WHOIS para {target}...")
        def worker(ctx):
            res = perform_whois_query(target)
            for line in res.splitlines():
                if line.strip():
                    ctx.on_log("INFO", line)
        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_ssl(self):
        target = self._get_target()
        self.log_panel.append_log("INFO", f"Verificando certificado SSL de {target}:443...")
        def worker(ctx):
            try:
                info = inspect_ssl_certificate(target)
                ctx.on_log("INFO", f"Domínio: {info.dominio}")
                ctx.on_log("INFO", f"Emissor: {info.emissor}")
                ctx.on_log("INFO", f"Validade: de {info.valido_de} até {info.valido_ate}")
                ctx.on_log("INFO", f"Tempo Restante: {info.dias_restantes}")
                ctx.on_log("INFO", f"Nomes Alternativos (SAN): {info.sans}")
            except Exception as e:
                ctx.on_log("ERROR", f"Falha ao inspecionar SSL: {str(e)}")
        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_site_check(self):
        target = self._get_target()
        self.log_panel.append_log("INFO", f"Verificando disponibilidade de {target}...")
        def worker(ctx):
            res = check_site_availability(target)
            lvl = "INFO" if res.is_online and res.status_code == 200 else ("WARN" if res.is_online else "ERROR")
            ctx.on_log(lvl, res.message)
        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )
