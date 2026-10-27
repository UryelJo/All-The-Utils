"""
Ferramenta: Consulta WHOIS de Domínios e IPs.
Permite inspecionar registrador, titularidade, expiração e nameservers de domínios públicos.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget, QMessageBox
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.whois.logic import (
    WhoisResult,
    normalize_domain,
    query_whois_socket,
)


@register
class WhoisLookupTool(Tool):
    id = "network.whois"
    name = "Consulta WHOIS de Domínios"
    category = "Rede e Internet"
    description = "Consulte titularidade, registrador, datas de criação e expiração de domínios de internet e IPs"
    keywords = ["whois", "dominio", "registro", "dns", "nameserver", "expiracao", "proprietario", "tld"]

    def __init__(self) -> None:
        super().__init__()
        self._current_result: Optional[WhoisResult] = None

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior de Entrada
        input_bar = QHBoxLayout()
        input_bar.setSpacing(10)

        self.txt_domain = QLineEdit()
        self.txt_domain.setPlaceholderText("Digite um domínio ou IP (ex: github.com, python.org, uol.com.br)...")
        self.txt_domain.setText("python.org")
        self.txt_domain.returnPressed.connect(self._run_lookup)
        input_bar.addWidget(self.txt_domain, stretch=1)

        self.btn_search = QPushButton("Consultar WHOIS")
        self.btn_search.setStyleSheet("font-weight: 600;")
        self.btn_search.clicked.connect(self._run_lookup)
        input_bar.addWidget(self.btn_search)

        main_layout.addLayout(input_bar)

        # Abas
        self.tabs = QTabWidget()

        # Aba 1: Resumo Estruturado
        tab_summary = QWidget()
        sum_layout = QVBoxLayout(tab_summary)
        sum_layout.setContentsMargins(12, 12, 12, 12)
        sum_layout.setSpacing(12)

        grp_info = QGroupBox("Dados do Registro")
        grid_info = QGridLayout(grp_info)
        grid_info.setHorizontalSpacing(16)
        grid_info.setVerticalSpacing(10)

        self.lbl_dom = QLabel("-")
        self.lbl_registrar = QLabel("-")
        self.lbl_owner = QLabel("-")
        self.lbl_status = QLabel("-")

        grid_info.addWidget(QLabel("<b>Domínio:</b>"), 0, 0)
        grid_info.addWidget(self.lbl_dom, 0, 1)
        grid_info.addWidget(QLabel("<b>Registrador:</b>"), 0, 2)
        grid_info.addWidget(self.lbl_registrar, 0, 3)

        grid_info.addWidget(QLabel("<b>Titular:</b>"), 1, 0)
        grid_info.addWidget(self.lbl_owner, 1, 1)
        grid_info.addWidget(QLabel("<b>Status:</b>"), 1, 2)
        grid_info.addWidget(self.lbl_status, 1, 3)
        sum_layout.addWidget(grp_info)

        # Datas
        grp_dates = QGroupBox("Ciclo de Vida do Domínio")
        grid_dates = QGridLayout(grp_dates)
        grid_dates.setHorizontalSpacing(16)
        grid_dates.setVerticalSpacing(10)

        self.lbl_created = QLabel("-")
        self.lbl_expires = QLabel("-")
        grid_dates.addWidget(QLabel("<b>Data de Criação:</b>"), 0, 0)
        grid_dates.addWidget(self.lbl_created, 0, 1)
        grid_dates.addWidget(QLabel("<b>Data de Expiração:</b>"), 0, 2)
        grid_dates.addWidget(self.lbl_expires, 0, 3)
        sum_layout.addWidget(grp_dates)

        # Nameservers
        grp_ns = QGroupBox("Servidores DNS Autoritativos (Nameservers)")
        ns_layout = QVBoxLayout(grp_ns)
        self.lbl_nameservers = QLabel("Nenhum servidor DNS listado")
        self.lbl_nameservers.setStyleSheet("color: #334155; font-family: monospace;")
        ns_layout.addWidget(self.lbl_nameservers)
        sum_layout.addWidget(grp_ns)

        sum_layout.addStretch()
        self.tabs.addTab(tab_summary, "Resumo Estruturado")

        # Aba 2: Resposta Completa
        tab_raw = QWidget()
        raw_layout = QVBoxLayout(tab_raw)
        raw_layout.setContentsMargins(8, 8, 8, 8)
        raw_layout.setSpacing(8)

        raw_top = QHBoxLayout()
        raw_top.addWidget(QLabel("Texto Bruto da Consulta RFC 3912:"))
        raw_top.addStretch()

        self.btn_copy_raw = QPushButton("Copiar Resposta")
        self.btn_copy_raw.clicked.connect(self._copy_raw)
        raw_top.addWidget(self.btn_copy_raw)
        raw_layout.addLayout(raw_top)

        self.txt_raw = QTextEdit()
        self.txt_raw.setReadOnly(True)
        self.txt_raw.setStyleSheet("font-family: monospace; font-size: 11px;")
        raw_layout.addWidget(self.txt_raw)

        self.tabs.addTab(tab_raw, "Resposta Bruta (Raw)")
        main_layout.addWidget(self.tabs)

        # Barra de Status
        self.lbl_footer = QLabel("Digite o domínio e clique em Consultar WHOIS.")
        self.lbl_footer.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_footer)

        return container

    def _run_lookup(self) -> None:
        target = self.txt_domain.text().strip()
        if not target:
            QMessageBox.warning(None, "Domínio obrigatório", "Por favor, informe um domínio para consulta.")
            return

        norm = normalize_domain(target)
        self.btn_search.setEnabled(False)
        self.lbl_footer.setText(f"Consultando servidor WHOIS para '{norm}'...")

        def _worker() -> WhoisResult:
            return query_whois_socket(norm)

        TaskRunner.run(
            _worker,
            on_success=self._on_lookup_success,
            on_error=self._on_lookup_error
        )

    def _on_lookup_success(self, res: WhoisResult) -> None:
        self._current_result = res
        self.btn_search.setEnabled(True)
        self.lbl_footer.setText(f"Consulta de '{res.domain}' finalizada com sucesso.")

        self.lbl_dom.setText(res.domain)
        self.lbl_registrar.setText(res.registrar)
        self.lbl_owner.setText(res.registrant)
        self.lbl_status.setText(res.status)
        self.lbl_created.setText(res.creation_date)
        self.lbl_expires.setText(res.expiration_date)

        if res.name_servers:
            self.lbl_nameservers.setText("\n".join(f"• {ns}" for ns in res.name_servers))
        else:
            self.lbl_nameservers.setText("Nenhum servidor DNS encontrado")

        self.txt_raw.setText(res.raw_text)

    def _on_lookup_error(self, err: Exception) -> None:
        self.btn_search.setEnabled(True)
        self.lbl_footer.setText(f"Falha na consulta: {err}")

    def _copy_raw(self) -> None:
        if self._current_result:
            QGuiApplication.clipboard().setText(self._current_result.raw_text)
            self.lbl_footer.setText("Resposta WHOIS copiada para a área de transferência!")
