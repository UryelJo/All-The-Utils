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

def inspect_ssl_certificate(hostname: str, port: int = 443) -> Dict[str, str]:
    """Inspeciona o certificado SSL/TLS de um domínio usando o módulo ssl nativo."""
    hostname = hostname.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=6) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()

    not_after_str = cert.get("notAfter", "")
    not_before_str = cert.get("notBefore", "")

    # Converte datas (formato padrão: 'May 10 12:00:00 2025 GMT')
    fmt = "%b %d %H:%M:%S %Y %Z"
    exp_date = datetime.datetime.strptime(not_after_str, fmt)
    start_date = datetime.datetime.strptime(not_before_str, fmt)
    days_left = (exp_date - datetime.datetime.utcnow()).days

    issuer_dict = dict(x[0] for x in cert.get("issuer", ()))
    subject_dict = dict(x[0] for x in cert.get("subject", ()))
    sans = [val for key, val in cert.get("subjectAltName", ()) if key == "DNS"]

    return {
        "dominio": hostname,
        "emissor": issuer_dict.get("organizationName") or issuer_dict.get("commonName", "Desconhecido"),
        "sujeito": subject_dict.get("commonName", hostname),
        "valido_de": start_date.strftime("%d/%m/%Y %H:%M UTC"),
        "valido_ate": exp_date.strftime("%d/%m/%Y %H:%M UTC"),
        "dias_restantes": f"{days_left} dias ({'Válido' if days_left > 0 else 'EXPIRADO'})",
        "sans": ", ".join(sans[:8]) + ("..." if len(sans) > 8 else "")
    }

def perform_whois_query(domain: str) -> str:
    """Executa consulta WHOIS via socket na porta 43."""
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0].strip()
    server = "whois.registro.br" if domain.endswith(".br") else "whois.iana.org"

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(6)
        s.connect((server, 43))
        s.send(f"{domain}\r\n".encode("utf-8"))
        response = b""
        while True:
            data = s.recv(4096)
            if not data:
                break
            response += data
        s.close()
        text = response.decode("utf-8", errors="replace")

        # Se for iana e indicar servidor específico (ex: verisign)
        if "whois:" in text.lower():
            for line in text.splitlines():
                if line.lower().startswith("whois:"):
                    sub_server = line.split(":", 1)[1].strip()
                    if sub_server and sub_server != server:
                        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s2.settimeout(6)
                        s2.connect((sub_server, 43))
                        s2.send(f"{domain}\r\n".encode("utf-8"))
                        resp2 = b""
                        while True:
                            d2 = s2.recv(4096)
                            if not d2:
                                break
                            resp2 += d2
                        s2.close()
                        return resp2.decode("utf-8", errors="replace")
        return text
    except Exception as e:
        return f"Erro ao consultar WHOIS em {server}: {str(e)}"

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

    def _run_ping(self):
        target = self._get_target()
        self.log_panel.append_log("INFO", f"Iniciando Ping para {target}...")
        cmd = f"ping -n 4 {target}"
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd, lambda line: ctx.on_log("INFO", line), shell=True),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_tracert(self):
        target = self._get_target()
        self.log_panel.append_log("INFO", f"Iniciando Traceroute para {target} (aguarde os saltos)...")
        cmd = f"tracert -d -h 15 {target}"
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd, lambda line: ctx.on_log("INFO", line), shell=True),
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_dns(self):
        target = self._get_target()
        self.log_panel.append_log("INFO", f"Consultando registros DNS para {target}...")
        cmd = f"nslookup {target}"
        self.runner.start_task(
            task_fn=lambda ctx: run_command_streaming(cmd, lambda line: ctx.on_log("INFO", line), shell=True),
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
                ctx.on_log("INFO", f"Domínio: {info['dominio']}")
                ctx.on_log("INFO", f"Emissor: {info['emissor']}")
                ctx.on_log("INFO", f"Validade: de {info['valido_de']} até {info['valido_ate']}")
                ctx.on_log("INFO", f"Tempo Restante: {info['dias_restantes']}")
                ctx.on_log("INFO", f"Nomes Alternativos (SAN): {info['sans']}")
            except Exception as e:
                ctx.on_log("ERROR", f"Falha ao inspecionar SSL: {str(e)}")
        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_site_check(self):
        target = self._get_target()
        url = target if target.startswith("http") else f"https://{target}"
        self.log_panel.append_log("INFO", f"Verificando disponibilidade de {url}...")
        def worker(ctx):
            t0 = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    elapsed = (time.time() - t0) * 1000
                    code = resp.getcode()
                    ctx.on_log("INFO", f"Status: {code} OK | Tempo de resposta: {elapsed:.0f} ms | Servidor Online!")
            except urllib.error.HTTPError as e:
                elapsed = (time.time() - t0) * 1000
                ctx.on_log("WARN", f"Status HTTP: {e.code} ({e.reason}) | Tempo: {elapsed:.0f} ms")
            except Exception as e:
                ctx.on_log("ERROR", f"Site Inacessível ou Offline: {str(e)}")
        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )
