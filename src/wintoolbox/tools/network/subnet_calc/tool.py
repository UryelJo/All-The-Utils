"""
Ferramenta: Calculadora de Sub-rede IPv4 e Notação CIDR.
Planeje redes, calcule faixas utilizáveis de hosts, broadcast e notação binária.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSlider,
    QSpinBox, QVBoxLayout, QWidget, QMessageBox
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.network.subnet_calc.logic import (
    SubnetDetails,
    calculate_subnet_details,
)


@register
class SubnetCalculatorTool(Tool):
    id = "network.subnet_calc"
    name = "Calculadora de Sub-rede IPv4"
    category = "Rede e Internet"
    description = "Calcule sub-redes CIDR, faixas de hosts utilizáveis, broadcast, wildcard e binário"
    keywords = ["sub-rede", "subnet", "cidr", "ip", "ipv4", "mascara", "broadcast", "hosts", "rfc1918"]

    def __init__(self) -> None:
        super().__init__()
        self._current_details: Optional[SubnetDetails] = None

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Painel de Entrada
        grp_input = QGroupBox("Parâmetros de Entrada")
        input_layout = QGridLayout(grp_input)
        input_layout.setHorizontalSpacing(14)
        input_layout.setVerticalSpacing(10)

        input_layout.addWidget(QLabel("Endereço IP:"), 0, 0)
        self.txt_ip = QLineEdit("192.168.1.100")
        self.txt_ip.textChanged.connect(self._recalculate)
        input_layout.addWidget(self.txt_ip, 0, 1)

        input_layout.addWidget(QLabel("Prefixo CIDR (/):"), 0, 2)
        self.spin_prefix = QSpinBox()
        self.spin_prefix.setRange(1, 32)
        self.spin_prefix.setValue(24)
        self.spin_prefix.valueChanged.connect(self._on_spin_changed)
        input_layout.addWidget(self.spin_prefix, 0, 3)

        # Slider de Máscara
        self.slider_prefix = QSlider(Qt.Horizontal)
        self.slider_prefix.setRange(1, 32)
        self.slider_prefix.setValue(24)
        self.slider_prefix.valueChanged.connect(self._on_slider_changed)
        input_layout.addWidget(self.slider_prefix, 1, 1, 1, 3)

        main_layout.addWidget(grp_input)

        # Grid de Resultados
        self.grp_results = QGroupBox("Resultados da Sub-rede")
        res_layout = QGridLayout(self.grp_results)
        res_layout.setHorizontalSpacing(16)
        res_layout.setVerticalSpacing(12)

        self.lbl_net_ip = QLabel("-")
        self.lbl_bcast_ip = QLabel("-")
        self.lbl_mask = QLabel("-")
        self.lbl_wildcard = QLabel("-")
        self.lbl_range = QLabel("-")
        self.lbl_usable = QLabel("-")
        self.lbl_total = QLabel("-")
        self.lbl_scope = QLabel("-")
        self.lbl_class = QLabel("-")
        self.lbl_bin_ip = QLabel("-")
        self.lbl_bin_mask = QLabel("-")

        # Configura estilo monospace para binários e IPs
        for lbl in (self.lbl_net_ip, self.lbl_bcast_ip, self.lbl_mask, self.lbl_wildcard,
                    self.lbl_range, self.lbl_bin_ip, self.lbl_bin_mask):
            lbl.setStyleSheet("font-family: monospace; font-size: 13px; font-weight: 500;")

        self.lbl_usable.setStyleSheet("font-size: 18px; font-weight: 700; color: #0284c7;")

        res_layout.addWidget(QLabel("<b>Endereço de Rede:</b>"), 0, 0)
        res_layout.addWidget(self.lbl_net_ip, 0, 1)

        res_layout.addWidget(QLabel("<b>Endereço de Broadcast:</b>"), 0, 2)
        res_layout.addWidget(self.lbl_bcast_ip, 0, 3)

        res_layout.addWidget(QLabel("<b>Máscara de Sub-rede:</b>"), 1, 0)
        res_layout.addWidget(self.lbl_mask, 1, 1)

        res_layout.addWidget(QLabel("<b>Máscara Curinga (Wildcard):</b>"), 1, 2)
        res_layout.addWidget(self.lbl_wildcard, 1, 3)

        res_layout.addWidget(QLabel("<b>Faixa Utilizável (Hosts):</b>"), 2, 0)
        res_layout.addWidget(self.lbl_range, 2, 1, 1, 3)

        res_layout.addWidget(QLabel("<b>Hosts Utilizáveis:</b>"), 3, 0)
        res_layout.addWidget(self.lbl_usable, 3, 1)

        res_layout.addWidget(QLabel("<b>Total de Endereços:</b>"), 3, 2)
        res_layout.addWidget(self.lbl_total, 3, 3)

        res_layout.addWidget(QLabel("<b>Tipo de Escopo:</b>"), 4, 0)
        res_layout.addWidget(self.lbl_scope, 4, 1)

        res_layout.addWidget(QLabel("<b>Classe IPv4:</b>"), 4, 2)
        res_layout.addWidget(self.lbl_class, 4, 3)

        res_layout.addWidget(QLabel("<b>IP em Binário:</b>"), 5, 0)
        res_layout.addWidget(self.lbl_bin_ip, 5, 1, 1, 3)

        res_layout.addWidget(QLabel("<b>Máscara em Binário:</b>"), 6, 0)
        res_layout.addWidget(self.lbl_bin_mask, 6, 1, 1, 3)

        main_layout.addWidget(self.grp_results)

        # Botão de Ação
        bottom_bar = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar Relatório de Sub-rede")
        self.btn_copy.clicked.connect(self._copy_summary)
        bottom_bar.addWidget(self.btn_copy)
        bottom_bar.addStretch()

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #dc2626; font-size: 11px;")
        bottom_bar.addWidget(self.lbl_status)
        main_layout.addLayout(bottom_bar)

        main_layout.addStretch()

        self._recalculate()
        return container

    def _on_spin_changed(self, val: int) -> None:
        self.slider_prefix.blockSignals(True)
        self.slider_prefix.setValue(val)
        self.slider_prefix.blockSignals(False)
        self._recalculate()

    def _on_slider_changed(self, val: int) -> None:
        self.spin_prefix.blockSignals(True)
        self.spin_prefix.setValue(val)
        self.spin_prefix.blockSignals(False)
        self._recalculate()

    def _recalculate(self) -> None:
        ip = self.txt_ip.text().strip()
        prefix = self.spin_prefix.value()

        if not ip:
            self._clear_results()
            return

        try:
            details = calculate_subnet_details(ip, str(prefix))
            self._current_details = details
            self.lbl_status.setText("")

            self.lbl_net_ip.setText(details.network_ip)
            self.lbl_bcast_ip.setText(details.broadcast_ip)
            self.lbl_mask.setText(f"{details.netmask} (/{details.prefix})")
            self.lbl_wildcard.setText(details.wildcard)

            if details.prefix >= 31:
                self.lbl_range.setText(f"{details.first_host} (ponto a ponto ou host único)")
            else:
                self.lbl_range.setText(f"{details.first_host}  até  {details.last_host}")

            self.lbl_usable.setText(f"{details.usable_hosts:,}".replace(",", "."))
            self.lbl_total.setText(f"{details.total_addresses:,}".replace(",", "."))
            self.lbl_scope.setText(details.scope_type)
            self.lbl_class.setText(details.ip_class)
            self.lbl_bin_ip.setText(details.ip_binary)
            self.lbl_bin_mask.setText(details.netmask_binary)

        except Exception as e:
            self.lbl_status.setText(f"Endereço IP inválido: {e}")
            self._current_details = None

    def _clear_results(self) -> None:
        for lbl in (self.lbl_net_ip, self.lbl_bcast_ip, self.lbl_mask, self.lbl_wildcard,
                    self.lbl_range, self.lbl_usable, self.lbl_total, self.lbl_scope,
                    self.lbl_class, self.lbl_bin_ip, self.lbl_bin_mask):
            lbl.setText("-")

    def _copy_summary(self) -> None:
        if not self._current_details:
            return
        d = self._current_details
        text = (
            f"RELATÓRIO DE SUB-REDE IPV4\n"
            f"Endereço IP: {d.ip}/{d.prefix}\n"
            f"Máscara: {d.netmask} (Wildcard: {d.wildcard})\n"
            f"Rede: {d.network_ip}\n"
            f"Broadcast: {d.broadcast_ip}\n"
            f"Faixa de Hosts: {d.first_host} - {d.last_host}\n"
            f"Total de Hosts Utilizáveis: {d.usable_hosts}\n"
            f"Escopo: {d.scope_type} | Classe: {d.ip_class}\n"
        )
        QGuiApplication.clipboard().setText(text)
        self.lbl_status.setText("Relatório de sub-rede copiado para a área de transferência!")
        self.lbl_status.setStyleSheet("color: #16a34a; font-size: 11px;")
