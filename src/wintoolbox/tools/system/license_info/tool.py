"""
Interface gráfica do Visualizador de Licença, Chave OEM e Ativação do Windows.
"""
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.license_info.logic import (
    get_oem_bios_product_key, get_windows_activation_status
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.license_info.ui")


@register
class LicenseInfoTool(Tool):
    id = "system.license_info"
    name = "Chave de Produto e Ativação do Windows"
    category = "Sistema"
    description = "Consulta da chave OEM gravada na placa-mãe (BIOS/UEFI) e status oficial de ativação do sistema"
    keywords = ["chave", "product key", "oem", "bios", "ativacao", "licenca", "windows 11", "serial"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return LicenseInfoView(self, parent)


class LicenseInfoView(QWidget):
    def __init__(self, tool: LicenseInfoTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._oem_key: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Card de Status de Ativação
        self.card_activation = QFrame()
        self.card_activation.setObjectName("Card")
        act_lay = QVBoxLayout(self.card_activation)
        act_lay.setContentsMargins(16, 16, 16, 16)
        act_lay.setSpacing(10)

        top_act = QHBoxLayout()
        self.lbl_edition = QLabel("Carregando edição do sistema...")
        self.lbl_edition.setStyleSheet("font-size: 15px; font-weight: bold;")
        top_act.addWidget(self.lbl_edition)

        top_act.addStretch()
        self.lbl_act_badge = QLabel("Consultando...")
        top_act.addWidget(self.lbl_act_badge)
        act_lay.addLayout(top_act)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("Status da Licença:"), 0, 0)
        self.lbl_lic_status = QLabel("-")
        grid.addWidget(self.lbl_lic_status, 0, 1)

        grid.addWidget(QLabel("Canal de Licenciamento:"), 1, 0)
        self.lbl_channel = QLabel("-")
        grid.addWidget(self.lbl_channel, 1, 1)

        grid.addWidget(QLabel("Chave Parcial Ativa:"), 2, 0)
        self.lbl_partial_key = QLabel("-")
        grid.addWidget(self.lbl_partial_key, 2, 1)

        act_lay.addLayout(grid)
        layout.addWidget(self.card_activation)

        # Card de Chave OEM da BIOS
        self.card_oem = QFrame()
        self.card_oem.setObjectName("Card")
        oem_lay = QVBoxLayout(self.card_oem)
        oem_lay.setContentsMargins(16, 16, 16, 16)
        oem_lay.setSpacing(10)

        lbl_oem_title = QLabel("Chave de Produto Original da BIOS/UEFI (MSDM):")
        lbl_oem_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        oem_lay.addWidget(lbl_oem_title)

        lbl_oem_desc = QLabel("Chave de fábrica vinculada à placa-mãe pelo fabricante do hardware. Útil para reinstalações limpas do Windows.")
        lbl_oem_desc.setStyleSheet("color: #888888;")
        lbl_oem_desc.setWordWrap(True)
        oem_lay.addWidget(lbl_oem_desc)

        key_row = QHBoxLayout()
        self.txt_key = QLineEdit()
        self.txt_key.setReadOnly(True)
        self.txt_key.setEchoMode(QLineEdit.Password)
        self.txt_key.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 13px;")
        key_row.addWidget(self.txt_key, stretch=1)

        self.btn_toggle_key = QPushButton("Mostrar")
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.btn_toggle_key)

        self.btn_copy_key = QPushButton("Copiar Chave")
        self.btn_copy_key.clicked.connect(self._copy_key)
        key_row.addWidget(self.btn_copy_key)

        oem_lay.addLayout(key_row)
        layout.addWidget(self.card_oem)

        # Botão de Atualizar
        btn_refresh = QPushButton("Atualizar Dados de Licença")
        btn_refresh.setFixedWidth(200)
        btn_refresh.clicked.connect(self._load_async)
        layout.addWidget(btn_refresh)

        layout.addStretch()
        self._load_async()

    def _load_async(self) -> None:
        def _worker():
            oem = get_oem_bios_product_key()
            status = get_windows_activation_status()
            return oem, status

        def _on_done(result):
            oem, status = result
            self._oem_key = oem

            # Preenche ativação
            self.lbl_edition.setText(status.get("edition", "Windows"))
            is_act = status.get("is_activated", False)
            if is_act:
                self.lbl_act_badge.setText("Ativado e Licenciado")
                self.lbl_act_badge.setStyleSheet("background-color: #107c41; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
            else:
                self.lbl_act_badge.setText("Ativação Pendente")
                self.lbl_act_badge.setStyleSheet("background-color: #d83b01; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")

            self.lbl_lic_status.setText(status.get("status_description", "-"))
            self.lbl_channel.setText(status.get("license_channel", "-"))
            pk = status.get("partial_product_key", "")
            self.lbl_partial_key.setText(f"XXXXX-XXXXX-XXXXX-XXXXX-{pk}" if pk else "Licença Digital vinculada")

            # Preenche chave OEM
            if oem:
                self.txt_key.setText(oem)
                self.btn_copy_key.setEnabled(True)
                self.btn_toggle_key.setEnabled(True)
            else:
                self.txt_key.setEchoMode(QLineEdit.Normal)
                self.txt_key.setText("Nenhuma chave OEM encontrada gravada na BIOS (Computador montado ou chave retail/digital).")
                self.btn_copy_key.setEnabled(False)
                self.btn_toggle_key.setEnabled(False)

        def _on_error(err):
            show_toast(self, f"Erro ao consultar licença: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _toggle_key_visibility(self) -> None:
        if self.txt_key.echoMode() == QLineEdit.Password:
            self.txt_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("Ocultar")
        else:
            self.txt_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("Mostrar")

    def _copy_key(self) -> None:
        if self._oem_key:
            QApplication.clipboard().setText(self._oem_key)
            show_toast(self, "Chave OEM copiada para a área de transferência!")
