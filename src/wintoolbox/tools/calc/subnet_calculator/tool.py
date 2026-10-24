"""
Interface gráfica da Calculadora de Sub-redes IPv4 / CIDR.
"""
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.subnet_calculator.logic import calculate_subnet
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("calc.subnet_calculator.ui")

CIDR_OPTIONS = [
    (8, "/8  —  255.0.0.0  (16.777.214 hosts)"),
    (16, "/16  —  255.255.0.0  (65.534 hosts)"),
    (20, "/20  —  255.255.240.0  (4.094 hosts)"),
    (21, "/21  —  255.255.248.0  (2.046 hosts)"),
    (22, "/22  —  255.255.252.0  (1.022 hosts)"),
    (23, "/23  —  255.255.254.0  (510 hosts)"),
    (24, "/24  —  255.255.255.0  (254 hosts)"),
    (25, "/25  —  255.255.255.128  (126 hosts)"),
    (26, "/26  —  255.255.255.192  (62 hosts)"),
    (27, "/27  —  255.255.255.224  (30 hosts)"),
    (28, "/28  —  255.255.255.240  (14 hosts)"),
    (29, "/29  —  255.255.255.248  (6 hosts)"),
    (30, "/30  —  255.255.255.252  (2 hosts - Ponto a Ponto)"),
    (31, "/31  —  255.255.255.254  (2 IPs - RFC 3021)"),
    (32, "/32  —  255.255.255.255  (1 Host Único)")
]


@register
class SubnetCalculatorTool(Tool):
    id = "calc.subnet_calculator"
    name = "Calculadora de Sub-redes IPv4"
    category = "Calculadoras"
    description = "Cálculo de sub-redes CIDR, faixas de IP, máscaras curinga, hosts utilizáveis e binário"
    keywords = ["subnet", "ip", "cidr", "rede", "mascara", "broadcast", "ipv4", "calculadora"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SubnetCalculatorView(self, parent)


class SubnetCalculatorView(QWidget):
    def __init__(self, tool: SubnetCalculatorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._last_report = ""
        self._fields: Dict[str, QLineEdit] = {}

        self._build_ui()
        self._calculate()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Calculadora de Sub-redes IPv4 / CIDR",
            "Análise e dimensionamento de redes locais, faixas de broadcast, primeiro/último host e notação binária."
        ))

        # 1. Entradas
        input_box = QGroupBox("Parâmetros da Rede")
        grid_in = QGridLayout(input_box)
        grid_in.setSpacing(8)

        grid_in.addWidget(QLabel("Endereço IP (com ou sem barra CIDR):"), 0, 0)
        self.edit_ip = QLineEdit("192.168.1.100")
        self.edit_ip.setFont(QFont("Cascadia Mono", 10))
        self.edit_ip.textChanged.connect(self._calculate)
        grid_in.addWidget(self.edit_ip, 0, 1)

        grid_in.addWidget(QLabel("Máscara de Sub-rede / CIDR:"), 0, 2)
        self.combo_cidr = QComboBox()
        for prefix, label in CIDR_OPTIONS:
            self.combo_cidr.addItem(label, prefix)
        # Seleciona /24 por padrão
        idx_24 = [p for p, _ in CIDR_OPTIONS].index(24)
        self.combo_cidr.setCurrentIndex(idx_24)
        self.combo_cidr.currentIndexChanged.connect(self._calculate)
        grid_in.addWidget(self.combo_cidr, 0, 3)

        btn_copy = QPushButton("Copiar Relatório Completo")
        btn_copy.setProperty("class", "primary")
        btn_copy.clicked.connect(self._copy_full_report)
        grid_in.addWidget(btn_copy, 0, 4)

        root.addWidget(input_box)

        # 2. Resultados
        res_box = QGroupBox("Resultados da Sub-rede")
        res_grid = QGridLayout(res_box)
        res_grid.setSpacing(8)

        labels = [
            ("network_address", "Endereço de Rede:", 0, 0),
            ("netmask", "Máscara de Sub-rede:", 0, 2),
            ("first_host", "Primeiro Host Utilizável:", 1, 0),
            ("last_host", "Último Host Utilizável:", 1, 2),
            ("broadcast_address", "Endereço de Broadcast:", 2, 0),
            ("wildcard_mask", "Máscara Curinga (Wildcard):", 2, 2),
            ("usable_hosts", "Hosts Utilizáveis:", 3, 0),
            ("total_ips", "Total de Endereços IP:", 3, 2),
            ("ip_class", "Classe do Endereço:", 4, 0),
            ("ip_type", "Tipo de Roteamento:", 4, 2),
            ("ip_binary", "IP em Notação Binária:", 5, 0),
            ("netmask_binary", "Máscara em Notação Binária:", 5, 2),
        ]

        for key, text, r, c in labels:
            res_grid.addWidget(QLabel(text), r, c)
            ledit = QLineEdit()
            ledit.setReadOnly(True)
            ledit.setFont(QFont("Cascadia Mono", 9))
            self._fields[key] = ledit
            res_grid.addWidget(ledit, r, c + 1)

        root.addWidget(res_box, stretch=1)

    def _calculate(self) -> None:
        raw_ip = self.edit_ip.text().strip()
        if not raw_ip:
            return

        # Se o usuário digitou a barra "/N" no próprio campo IP
        if "/" in raw_ip:
            cidr_val = None
        else:
            cidr_val = str(self.combo_cidr.currentData())

        try:
            data = calculate_subnet(raw_ip, cidr_val)

            for key, ledit in self._fields.items():
                if key in data:
                    val = str(data[key])
                    if key in ("usable_hosts", "total_ips"):
                        val = f"{int(val):,}".replace(",", ".")
                    ledit.setText(val)

            # Destaca hosts utilizáveis
            self._fields["usable_hosts"].setStyleSheet("color: #10B981; font-weight: bold;")
            self._fields["network_address"].setStyleSheet("color: #60A5FA; font-weight: bold;")

            # Monta relatório
            self._last_report = (
                f"=== Relatório de Sub-rede IPv4 ===\n"
                f"Endereço Analisado: {data['ip']}{data['cidr_prefix']}\n"
                f"Rede: {data['network_address']}\n"
                f"Máscara: {data['netmask']} ({data['cidr_prefix']})\n"
                f"Máscara Curinga: {data['wildcard_mask']}\n"
                f"Faixa de Hosts: {data['first_host']} até {data['last_host']}\n"
                f"Broadcast: {data['broadcast_address']}\n"
                f"Hosts Utilizáveis: {data['usable_hosts']:,}\n"
                f"Classe / Tipo: {data['ip_class']} — {data['ip_type']}\n"
                f"Binário do IP: {data['ip_binary']}\n"
                f"Binário da Máscara: {data['netmask_binary']}\n"
            )

        except Exception as exc:
            for ledit in self._fields.values():
                ledit.setText("Inválido")
                ledit.setStyleSheet("color: #EF4444;")

    def _copy_full_report(self) -> None:
        if self._last_report:
            QApplication.clipboard().setText(self._last_report)
            show_toast(self, "Relatório copiado para a área de transferência!")
