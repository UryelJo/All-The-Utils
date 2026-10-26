"""
Ferramenta: Visualizador de Senhas Wi-Fi e Gerador de QR Code.
Lê perfis salvos via netsh e gera QR Code para conexão direta no celular.
"""
import io
import subprocess
from typing import Dict, List, Optional
import qrcode
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)
from .logic import WifiProfileItem, generate_wifi_qr_image, get_saved_wifi_profiles

def generate_wifi_qr_pixmap(ssid: str, password: str, auth_type: str = "WPA") -> QPixmap:
    """Converte o PIL Image gerado pela logic.py em QPixmap para a interface Qt."""
    pil_img = generate_wifi_qr_image(ssid, password, auth_type)
    data = pil_img.tobytes("raw", "RGB")
    qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)

@register
class WifiTool(Tool):
    id = "network.wifi"
    name = "Senhas Wi-Fi e QR Code"
    category = "Rede e Internet"
    description = "Visualização de senhas de redes Wi-Fi salvas e gerador de QR Code para conexão móvel"
    keywords = ["wifi", "wi-fi", "senha", "qr", "qrcode", "netsh", "sem fio", "rede", "compartilhar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return WifiView(self, parent)

class WifiView(QWidget):
    def __init__(self, tool: WifiTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._profiles: List[Dict[str, str]] = []
        self._current_qr_pixmap: Optional[QPixmap] = None

        self._build_ui()
        self._load_profiles()

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

        # ABA 1: Senhas Salvas
        tab_list = QWidget()
        l_list = QVBoxLayout(tab_list)
        l_list.setSpacing(10)

        row_actions = QHBoxLayout()
        btn_refresh = QPushButton("Atualizar Redes Wi-Fi")
        btn_refresh.clicked.connect(self._load_profiles)
        row_actions.addWidget(btn_refresh)

        btn_copy = QPushButton("Copiar Senha Selecionada")
        btn_copy.clicked.connect(self._copy_selected_password)
        row_actions.addWidget(btn_copy)

        btn_to_qr = QPushButton("Gerar QR Code desta Rede")
        btn_to_qr.clicked.connect(self._send_to_qr_tab)
        row_actions.addWidget(btn_to_qr)

        row_actions.addStretch()
        l_list.addLayout(row_actions)

        self.table_wifi = QTableWidget(0, 3)
        self.table_wifi.setHorizontalHeaderLabels(["Nome da Rede (SSID)", "Segurança", "Senha Salva"])
        self.table_wifi.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_wifi.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_wifi.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_wifi.verticalHeader().setVisible(False)
        self.table_wifi.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_wifi.setFixedHeight(260)
        enable_sorting_on_table(self.table_wifi)
        l_list.addWidget(self.table_wifi)

        tabs.addTab(tab_list, "Senhas Wi-Fi Salvas")

        # ABA 2: Gerador de QR Code
        tab_qr = QWidget()
        l_qr = QVBoxLayout(tab_qr)
        l_qr.setSpacing(10)

        card_form = QFrame()
        card_form.setProperty("class", "card")
        l_form = QVBoxLayout(card_form)
        l_form.setSpacing(8)

        row_f1 = QHBoxLayout()
        row_f1.addWidget(QLabel("Nome da Rede (SSID):"))
        self.txt_qr_ssid = QLineEdit()
        row_f1.addWidget(self.txt_qr_ssid)

        row_f1.addWidget(QLabel("Segurança:"))
        self.cmb_qr_auth = QComboBox()
        self.cmb_qr_auth.addItems(["WPA", "WPA2", "WPA3", "WEP", "Aberta"])
        row_f1.addWidget(self.cmb_qr_auth)
        l_form.addLayout(row_f1)

        row_f2 = QHBoxLayout()
        row_f2.addWidget(QLabel("Senha do Wi-Fi:"))
        self.txt_qr_pass = QLineEdit()
        self.txt_qr_pass.setEchoMode(QLineEdit.Normal)
        row_f2.addWidget(self.txt_qr_pass)

        btn_generate = QPushButton("Gerar QR Code")
        btn_generate.setProperty("class", "primary")
        btn_generate.clicked.connect(self._generate_qr)
        row_f2.addWidget(btn_generate)
        l_form.addLayout(row_f2)

        l_qr.addWidget(card_form)

        # Exibição do QR Code
        self.lbl_qr_display = QLabel("O QR Code gerado será exibido aqui.")
        self.lbl_qr_display.setAlignment(Qt.AlignCenter)
        self.lbl_qr_display.setFixedHeight(240)
        l_qr.addWidget(self.lbl_qr_display)

        self.btn_save_qr = QPushButton("Salvar Imagem do QR Code (PNG)...")
        self.btn_save_qr.setEnabled(False)
        self.btn_save_qr.clicked.connect(self._save_qr_image)
        l_qr.addWidget(self.btn_save_qr)

        tabs.addTab(tab_qr, "Gerador de QR Code Wi-Fi")
        self.tabs = tabs

        layout.addWidget(tabs)
        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _get_selected_profile(self) -> Optional[WifiProfileItem]:
        row = self.table_wifi.currentRow()
        if row >= 0:
            it = self.table_wifi.item(row, 0)
            if it:
                d = it.data(Qt.UserRole)
                if isinstance(d, WifiProfileItem):
                    return d
        if 0 <= row < len(self._profiles):
            return self._profiles[row]
        return None

    def _load_profiles(self):
        self._profiles = get_saved_wifi_profiles()
        with batch_table_update(self.table_wifi):
            self.table_wifi.setRowCount(len(self._profiles))
            for row, p in enumerate(self._profiles):
                self.table_wifi.setItem(row, 0, SmartTableWidgetItem(p.ssid, user_data=p))
                self.table_wifi.setItem(row, 1, SmartTableWidgetItem(p.auth))
                self.table_wifi.setItem(row, 2, SmartTableWidgetItem(p.password))

    def _copy_selected_password(self):
        p = self._get_selected_profile()
        if p:
            pwd = p.password
            QApplication.clipboard().setText(pwd)
            QMessageBox.information(self, "Copiado", f"Senha da rede '{p.ssid}' copiada para a área de transferência!")

    def _send_to_qr_tab(self):
        p = self._get_selected_profile()
        if p:
            self.txt_qr_ssid.setText(p.ssid)
            is_open = p.password == "(Sem senha / Aberta)"
            self.txt_qr_pass.setText("" if is_open else p.password)
            # Sem isso, uma rede aberta gerava QR "WPA" com senha vazia (o celular não conecta)
            self.cmb_qr_auth.setCurrentText("Aberta" if is_open else ("WEP" if "WEP" in p.auth.upper() else "WPA"))
            self.tabs.setCurrentIndex(1)
            self._generate_qr()

    def _generate_qr(self):
        ssid = self.txt_qr_ssid.text().strip()
        pwd = self.txt_qr_pass.text()
        auth = self.cmb_qr_auth.currentText()
        if not ssid:
            QMessageBox.warning(self, "Aviso", "Por favor, informe o nome da rede (SSID).")
            return

        pix = generate_wifi_qr_pixmap(ssid, pwd, auth)
        self._current_qr_pixmap = pix
        self.lbl_qr_display.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.btn_save_qr.setEnabled(True)

    def _save_qr_image(self):
        if not self._current_qr_pixmap:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar QR Code", f"wifi_{self.txt_qr_ssid.text()}.png", "Imagem PNG (*.png)")
        if path:
            self._current_qr_pixmap.save(path, "PNG")
            QMessageBox.information(self, "Sucesso", "Imagem do QR Code salva com sucesso!")
