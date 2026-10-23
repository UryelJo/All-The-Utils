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

def get_saved_wifi_profiles() -> List[Dict[str, str]]:
    """Recupera redes Wi-Fi e senhas salvas no Windows via netsh."""
    profiles = []
    try:
        out = subprocess.check_output(
            "netsh wlan show profiles",
            shell=True,
            text=True,
            errors="replace"
        )
        profile_names = []
        for line in out.splitlines():
            if ":" in line and ("Todos os Perfis de Usurios" in line or "All User Profile" in line or "Perfil de Todos os Usurios" in line or "Perfil" in line):
                p_name = line.split(":", 1)[1].strip()
                if p_name:
                    profile_names.append(p_name)

        for name in profile_names:
            try:
                cmd = f'netsh wlan show profile name="{name}" key=clear'
                p_out = subprocess.check_output(cmd, shell=True, text=True, errors="replace")
                auth = "WPA2"
                key = "(Sem senha / Aberta)"
                for pline in p_out.splitlines():
                    if ":" in pline:
                        k, v = pline.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if "Autenticao" in k or "Authentication" in k:
                            auth = v
                        elif "Contedo da Chave" in k or "Key Content" in k:
                            key = v
                profiles.append({
                    "ssid": name,
                    "auth": auth,
                    "password": key
                })
            except Exception:
                continue
    except Exception:
        pass
    return profiles

def generate_wifi_qr_pixmap(ssid: str, password: str, auth_type: str = "WPA") -> QPixmap:
    """Gera o QR code para conexão automática de celular ao Wi-Fi."""
    # Padrão universal: WIFI:T:WPA;S:rede;P:senha;;
    if auth_type == "Aberta":
        payload = f"WIFI:S:{ssid};T:nopass;;"
    else:
        payload = f"WIFI:T:{auth_type};S:{ssid};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Converte PIL Image para QPixmap
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

    def _load_profiles(self):
        self._profiles = get_saved_wifi_profiles()
        self.table_wifi.setRowCount(len(self._profiles))
        for row, p in enumerate(self._profiles):
            self.table_wifi.setItem(row, 0, QTableWidgetItem(p["ssid"]))
            self.table_wifi.setItem(row, 1, QTableWidgetItem(p["auth"]))
            self.table_wifi.setItem(row, 2, QTableWidgetItem(p["password"]))

    def _copy_selected_password(self):
        row = self.table_wifi.currentRow()
        if row >= 0 and row < len(self._profiles):
            pwd = self._profiles[row]["password"]
            QApplication.clipboard().setText(pwd)
            QMessageBox.information(self, "Copiado", f"Senha da rede '{self._profiles[row]['ssid']}' copiada para a área de transferência!")

    def _send_to_qr_tab(self):
        row = self.table_wifi.currentRow()
        if row >= 0 and row < len(self._profiles):
            p = self._profiles[row]
            self.txt_qr_ssid.setText(p["ssid"])
            self.txt_qr_pass.setText(p["password"] if p["password"] != "(Sem senha / Aberta)" else "")
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
