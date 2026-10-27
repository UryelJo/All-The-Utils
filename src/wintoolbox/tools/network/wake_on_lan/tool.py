"""
Ferramenta: Wake-on-LAN (WOL).
Permite ligar computadores remotamente enviando pacotes mágicos (Magic Packets) na rede local.
"""
from typing import Any, Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.network.wake_on_lan.logic import (
    load_saved_wol_devices,
    normalize_mac_address,
    save_wol_devices,
    send_magic_packet,
)


@register
class WakeOnLanTool(Tool):
    id = "network.wake_on_lan"
    name = "Wake-on-LAN (WOL)"
    category = "Rede e Internet"
    description = "Envie Magic Packets para ligar computadores e servidores na rede local com lista de favoritos"
    keywords = ["wol", "wake on lan", "magic packet", "ligar pc", "remoto", "mac", "broadcast", "udp"]

    def __init__(self) -> None:
        super().__init__()
        self._devices: List[Dict[str, Any]] = []

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Painel Superior: Envio e Cadastro
        grp_send = QGroupBox("Disparo de Pacote Mágico (Magic Packet)")
        send_layout = QVBoxLayout(grp_send)
        send_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        # Nome
        grid.addWidget(QLabel("Nome do Dispositivo:"), 0, 0)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ex: Servidor de Arquivos, PC Escritório")
        grid.addWidget(self.txt_name, 0, 1)

        # MAC
        grid.addWidget(QLabel("Endereço MAC:"), 0, 2)
        self.txt_mac = QLineEdit()
        self.txt_mac.setPlaceholderText("Ex: 00:11:22:33:44:55 ou 00-11-22-33-44-55")
        grid.addWidget(self.txt_mac, 0, 3)

        # IP Broadcast
        grid.addWidget(QLabel("IP de Broadcast:"), 1, 0)
        self.txt_ip = QLineEdit("255.255.255.255")
        grid.addWidget(self.txt_ip, 1, 1)

        # Porta
        grid.addWidget(QLabel("Porta UDP:"), 1, 2)
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(9)
        grid.addWidget(self.spin_port, 1, 3)

        send_layout.addLayout(grid)

        # Botões de Ação
        btn_box = QHBoxLayout()
        self.btn_send_now = QPushButton("Enviar Pacote Wake-on-LAN")
        self.btn_send_now.setStyleSheet("font-weight: 600;")
        self.btn_send_now.clicked.connect(self._send_now)
        btn_box.addWidget(self.btn_send_now)

        self.btn_save_device = QPushButton("Salvar Dispositivo na Lista")
        self.btn_save_device.clicked.connect(self._save_device)
        btn_box.addWidget(self.btn_save_device)

        btn_box.addStretch()
        send_layout.addLayout(btn_box)

        main_layout.addWidget(grp_send)

        # Tabela de Dispositivos Favoritos
        grp_favs = QGroupBox("Dispositivos Salvos")
        favs_layout = QVBoxLayout(grp_favs)
        favs_layout.setSpacing(8)

        favs_actions = QHBoxLayout()
        self.btn_wake_selected = QPushButton("Despertar Selecionado")
        self.btn_wake_selected.clicked.connect(self._wake_selected)
        favs_actions.addWidget(self.btn_wake_selected)

        self.btn_remove_selected = QPushButton("Remover da Lista")
        self.btn_remove_selected.clicked.connect(self._remove_selected)
        favs_actions.addWidget(self.btn_remove_selected)

        favs_actions.addStretch()
        favs_layout.addLayout(favs_actions)

        columns = [
            Column("name", "Nome", width=220),
            Column("mac", "Endereço MAC", width=180),
            Column("ip", "Broadcast IP", width=160),
            Column("port", "Porta UDP", width=110),
        ]
        self.table = DataTableView(columns, key="mac", parent=grp_favs)
        favs_layout.addWidget(self.table)

        main_layout.addWidget(grp_favs)

        # Status
        self.lbl_status = QLabel("Preencha o MAC do computador e envie o pacote de ativação.")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_status)

        self._load_saved()
        return container

    def _load_saved(self) -> None:
        self._devices = load_saved_wol_devices()
        self.table.set_records(self._devices)

    def _send_now(self) -> None:
        mac = self.txt_mac.text().strip()
        ip = self.txt_ip.text().strip()
        port = self.spin_port.value()

        if not mac:
            QMessageBox.warning(None, "MAC Obrigatório", "Por favor, informe o endereço MAC do dispositivo.")
            return

        ok, msg = send_magic_packet(mac, broadcast_ip=ip, port=port)
        if ok:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")
        else:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 600; font-size: 12px;")

    def _save_device(self) -> None:
        name = self.txt_name.text().strip() or "Dispositivo Sem Nome"
        mac = self.txt_mac.text().strip()
        ip = self.txt_ip.text().strip()
        port = self.spin_port.value()

        try:
            norm_mac = normalize_mac_address(mac)
        except ValueError as e:
            QMessageBox.warning(None, "MAC Inválido", str(e))
            return

        # Verifica se já existe
        for d in self._devices:
            if d.get("mac") == norm_mac:
                d["name"] = name
                d["ip"] = ip
                d["port"] = port
                break
        else:
            self._devices.append({
                "name": name,
                "mac": norm_mac,
                "ip": ip,
                "port": port
            })

        save_wol_devices(self._devices)
        self.table.set_records(self._devices)
        self.lbl_status.setText(f"Dispositivo '{name}' ({norm_mac}) salvo com sucesso!")
        self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")

    def _wake_selected(self) -> None:
        rec = self.table.current_record()
        if not rec:
            QMessageBox.information(None, "Seleção necessária", "Selecione um dispositivo na tabela para despertar.")
            return

        mac = rec["mac"]
        ip = rec.get("ip") or "255.255.255.255"
        port = int(rec.get("port") or 9)

        ok, msg = send_magic_packet(mac, broadcast_ip=ip, port=port)
        if ok:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")
        else:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 600; font-size: 12px;")

    def _remove_selected(self) -> None:
        rec = self.table.current_record()
        if not rec:
            return

        mac = rec["mac"]
        self._devices = [d for d in self._devices if d.get("mac") != mac]
        save_wol_devices(self._devices)
        self.table.set_records(self._devices)
        self.lbl_status.setText("Dispositivo removido da lista.")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
