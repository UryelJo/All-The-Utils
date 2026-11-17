"""
Interface gráfica do Visualizador de Licença, Chave OEM e Ativação do Windows 10 e 11.
"""
import os
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.license_info.logic import (
    WINDOWS_10_11_EDITION_KEYS,
    activate_windows_online,
    check_activation_expiration,
    get_oem_bios_product_key,
    get_windows_activation_status,
    install_product_key,
    set_kms_server,
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.license_info.ui")


@register
class LicenseInfoTool(Tool):
    id = "system.license_info"
    name = "Chave de Produto e Ativação do Windows"
    category = "Sistema"
    description = "Consulta da chave OEM da placa-mãe (BIOS/UEFI) e opções de ativação para Windows 10 e Windows 11"
    keywords = ["chave", "product key", "oem", "bios", "ativacao", "licenca", "windows 11", "windows 10", "serial", "slmgr"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return LicenseInfoView(self, parent)


class LicenseInfoView(QWidget):
    def __init__(self, tool: LicenseInfoTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._oem_key: Optional[str] = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        # 1. Card de Status de Ativação
        self.card_activation = QFrame()
        self.card_activation.setObjectName("Card")
        self.card_activation.setProperty("class", "card")
        act_lay = QVBoxLayout(self.card_activation)
        act_lay.setContentsMargins(16, 14, 16, 14)
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

        act_btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Atualizar Status de Licença")
        btn_refresh.clicked.connect(self._load_async)
        act_btn_row.addWidget(btn_refresh)

        btn_xpr = QPushButton("Verificar Validade da Ativação (slmgr /xpr)")
        btn_xpr.clicked.connect(self._on_check_expiration)
        act_btn_row.addWidget(btn_xpr)

        btn_win_settings = QPushButton("Abrir Configurações de Ativação do Windows")
        btn_win_settings.clicked.connect(lambda: os.startfile("ms-settings:activation"))
        act_btn_row.addWidget(btn_win_settings)
        act_btn_row.addStretch()
        act_lay.addLayout(act_btn_row)

        layout.addWidget(self.card_activation)

        # 2. Card de Chave OEM da BIOS
        self.card_oem = QFrame()
        self.card_oem.setObjectName("Card")
        self.card_oem.setProperty("class", "card")
        oem_lay = QVBoxLayout(self.card_oem)
        oem_lay.setContentsMargins(16, 14, 16, 14)
        oem_lay.setSpacing(8)

        lbl_oem_title = QLabel("Chave de Produto Original da BIOS/UEFI (MSDM):")
        lbl_oem_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        oem_lay.addWidget(lbl_oem_title)

        lbl_oem_desc = QLabel(
            "Chave de fábrica vinculada à placa-mãe pelo fabricante (compatível com Windows 10 e Windows 11)."
        )
        lbl_oem_desc.setProperty("class", "secondary")
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

        self.btn_use_oem = QPushButton("Aplicar Chave da BIOS")
        self.btn_use_oem.clicked.connect(self._use_oem_key)
        key_row.addWidget(self.btn_use_oem)

        oem_lay.addLayout(key_row)
        layout.addWidget(self.card_oem)

        # 3. Gerenciamento de Ativação (Windows 10 e Windows 11)
        grp_activate = QGroupBox("Opções de Ativação — Windows 10 e Windows 11")
        act_ops_lay = QVBoxLayout(grp_activate)
        act_ops_lay.setSpacing(10)

        lbl_info = QLabel(
            "As chaves de produto e licenças digitais da Microsoft são unificadas entre o Windows 10 e o Windows 11 "
            "para a mesma edição (Home, Pro, Enterprise, Education). Você pode selecionar uma chave genérica/KMS oficial "
            "abaixo ou digitar sua própria chave Retail/OEM/MAK."
        )
        lbl_info.setProperty("class", "secondary")
        lbl_info.setWordWrap(True)
        act_ops_lay.addWidget(lbl_info)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Chaves Oficiais por Edição (Win 10 / Win 11):"))
        self.cmb_edition_keys = QComboBox()
        self.cmb_edition_keys.addItem("-- Selecionar edição para preencher a chave --", "")
        for item in WINDOWS_10_11_EDITION_KEYS:
            self.cmb_edition_keys.addItem(f"{item['edition']} ({item['key']})", item["key"])
        self.cmb_edition_keys.currentIndexChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self.cmb_edition_keys, stretch=1)
        act_ops_lay.addLayout(preset_row)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Chave de Produto (25 dígitos):"))
        self.txt_install_key = QLineEdit()
        self.txt_install_key.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self.txt_install_key.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace;")
        input_row.addWidget(self.txt_install_key, stretch=1)

        self.btn_install_key = QPushButton("1. Instalar Chave (slmgr /ipk)")
        self.btn_install_key.setProperty("class", "primary")
        self.btn_install_key.clicked.connect(self._on_install_key)
        input_row.addWidget(self.btn_install_key)

        self.btn_activate_now = QPushButton("2. Ativar Windows Agora (slmgr /ato)")
        self.btn_activate_now.setProperty("accent", True)
        self.btn_activate_now.clicked.connect(self._on_activate_online)
        input_row.addWidget(self.btn_activate_now)

        act_ops_lay.addLayout(input_row)

        kms_row = QHBoxLayout()
        kms_row.addWidget(QLabel("Servidor KMS Corporativo (opcional):"))
        self.txt_kms_host = QLineEdit()
        self.txt_kms_host.setPlaceholderText("Ex: kms.empresa.local (apenas para licenciamento por volume KMS)")
        kms_row.addWidget(self.txt_kms_host, stretch=1)

        self.btn_set_kms = QPushButton("Definir Servidor KMS (slmgr /skms)")
        self.btn_set_kms.clicked.connect(self._on_set_kms)
        kms_row.addWidget(self.btn_set_kms)
        act_ops_lay.addLayout(kms_row)

        layout.addWidget(grp_activate)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._load_async()

    def _on_preset_selected(self):
        key = self.cmb_edition_keys.currentData()
        if key:
            self.txt_install_key.setText(key)

    def _use_oem_key(self):
        if self._oem_key:
            self.txt_install_key.setText(self._oem_key)
            show_toast(self, "Chave OEM preenchida no campo de instalação!")

    def _load_async(self) -> None:
        def _worker():
            oem = get_oem_bios_product_key()
            status = get_windows_activation_status()
            return oem, status

        def _on_done(result):
            oem, status = result
            self._oem_key = oem

            self.lbl_edition.setText(status.get("edition", "Windows"))
            is_act = status.get("is_activated", False)
            if is_act:
                self.lbl_act_badge.setText("Ativado e Licenciado")
                self.lbl_act_badge.setStyleSheet(
                    "background-color: #107c41; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;"
                )
            else:
                self.lbl_act_badge.setText("Ativação Pendente")
                self.lbl_act_badge.setStyleSheet(
                    "background-color: #d83b01; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;"
                )

            self.lbl_lic_status.setText(status.get("status_description", "-"))
            self.lbl_channel.setText(status.get("license_channel", "-"))
            pk = status.get("partial_product_key", "")
            self.lbl_partial_key.setText(f"XXXXX-XXXXX-XXXXX-XXXXX-{pk}" if pk else "Licença Digital vinculada")

            if oem:
                self.txt_key.setText(oem)
                self.btn_copy_key.setEnabled(True)
                self.btn_toggle_key.setEnabled(True)
                self.btn_use_oem.setEnabled(True)
            else:
                self.txt_key.setEchoMode(QLineEdit.Normal)
                self.txt_key.setText(
                    "Nenhuma chave OEM encontrada gravada na BIOS (Computador montado ou licença retail/digital)."
                )
                self.btn_copy_key.setEnabled(False)
                self.btn_toggle_key.setEnabled(False)
                self.btn_use_oem.setEnabled(False)

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

    def _require_admin_for_slmgr(self, action_desc: str) -> bool:
        if is_admin():
            return True
        prompt_elevation_dialog(
            self,
            tool_name=self.tool.name,
            reason=f"Para {action_desc} via Gerenciador de Licenciamento do Windows (slmgr), são necessários privilégios de Administrador.",
        )
        return False

    def _on_install_key(self) -> None:
        key = self.txt_install_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Aviso", "Digite ou selecione uma chave de produto de 25 caracteres.")
            return
        if not self._require_admin_for_slmgr("instalar uma chave de produto"):
            return

        self.btn_install_key.setEnabled(False)
        TaskRunner.run(
            lambda: install_product_key(key),
            on_success=self._on_slmgr_done,
            on_error=lambda err: self._on_slmgr_done((False, str(err))),
        )

    def _on_activate_online(self) -> None:
        if not self._require_admin_for_slmgr("ativar o Windows"):
            return
        self.btn_activate_now.setEnabled(False)
        TaskRunner.run(
            activate_windows_online,
            on_success=self._on_slmgr_done,
            on_error=lambda err: self._on_slmgr_done((False, str(err))),
        )

    def _on_set_kms(self) -> None:
        host = self.txt_kms_host.text().strip()
        if not host:
            QMessageBox.warning(self, "Aviso", "Informe o endereço do servidor KMS.")
            return
        if not self._require_admin_for_slmgr("configurar o servidor KMS"):
            return
        self.btn_set_kms.setEnabled(False)
        TaskRunner.run(
            lambda: set_kms_server(host),
            on_success=self._on_slmgr_done,
            on_error=lambda err: self._on_slmgr_done((False, str(err))),
        )

    def _on_check_expiration(self) -> None:
        TaskRunner.run(
            check_activation_expiration,
            on_success=lambda res: QMessageBox.information(self, "Validade da Licença (slmgr /xpr)", res[1]),
            on_error=lambda err: QMessageBox.warning(self, "Aviso", str(err)),
        )

    def _on_slmgr_done(self, result) -> None:
        self.btn_install_key.setEnabled(True)
        self.btn_activate_now.setEnabled(True)
        self.btn_set_kms.setEnabled(True)
        ok, msg = result
        if ok:
            QMessageBox.information(self, "Gerenciador de Licença do Windows", msg)
            self._load_async()
        else:
            QMessageBox.warning(self, "Aviso do Sistema de Licenciamento", msg)
