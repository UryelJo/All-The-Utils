"""
Ferramenta: Servidor HTTP Local e Compartilhamento de Arquivos com QR Code.
Permite compartilhar qualquer pasta do PC na rede local e acessar via celular/outros dispositivos.
"""
import io
import os
import socket
import threading
import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional
import qrcode
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.ui.widgets.log_panel import LogPanelWidget

def get_primary_local_ip() -> str:
    """Descobre o endereço IPv4 principal da máquina na rede local."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Não precisa alcançar a internet de fato, só força a escolha da interface de saída
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class LoggingHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, log_callback=None, directory=None, **kwargs):
        self.log_callback = log_callback
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        if self.log_callback:
            msg = f"{self.client_address[0]} - {format % args}"
            self.log_callback("INFO", msg)

    def do_POST(self):
        """Recebe upload de arquivos vindos do celular ou outro dispositivo na mesma rede."""
        if self.path == "/__wintoolbox_upload":
            content_type = self.headers.get("Content-Type", "")
            content_length = int(self.headers.get("Content-Length", 0))

            if "multipart/form-data" in content_type and content_length > 0:
                boundary = content_type.split("boundary=")[1].strip().encode()
                body = self.rfile.read(content_length)
                parts = body.split(b"--" + boundary)

                for part in parts:
                    if b'filename="' in part:
                        headers_part, file_data = part.split(b"\r\n\r\n", 1)
                        if file_data.endswith(b"\r\n"):
                            file_data = file_data[:-2]

                        fn_start = headers_part.find(b'filename="') + 10
                        fn_end = headers_part.find(b'"', fn_start)
                        filename = headers_part[fn_start:fn_end].decode("utf-8", errors="ignore")
                        filename = os.path.basename(filename)

                        if filename:
                            target_file = Path(self.directory) / filename
                            with open(target_file, "wb") as f:
                                f.write(file_data)
                            if self.log_callback:
                                self.log_callback("INFO", f"Arquivo recebido via LAN: {filename} ({len(file_data)} bytes)")

                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return

        self.send_error(400, "Requisição de upload inválida.")

    def list_directory(self, path):
        """Injeta um formulário de upload responsivo no topo da listagem de diretório."""
        f = super().list_directory(path)
        if f is None:
            return None

        content = f.read().decode("utf-8", errors="replace")
        f.close()

        upload_ui = (
            '<div style="background:#202020;color:#ffffff;padding:16px 20px;margin:16px 0;border-radius:8px;font-family:Segoe UI,system-ui,sans-serif;box-shadow:0 4px 12px rgba(0,0,0,0.15);">'
            '<h3 style="margin:0 0 6px 0;font-size:16px;color:#0078d4;">WinToolbox — Transferência Local de Arquivos</h3>'
            '<p style="font-size:13px;color:#cccccc;margin:0 0 12px 0;">Envie fotos, documentos ou qualquer arquivo do seu celular ou tablet diretamente para este computador:</p>'
            '<form method="POST" action="/__wintoolbox_upload" enctype="multipart/form-data" style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">'
            '<input type="file" name="file" required style="padding:8px 12px;background:#2d2d2d;color:#ffffff;border:1px solid #444;border-radius:4px;font-size:13px;">'
            '<button type="submit" style="padding:8px 18px;background:#0078d4;color:#ffffff;border:none;border-radius:4px;font-weight:600;font-size:13px;cursor:pointer;">Enviar para este PC</button>'
            '</form>'
            '</div>'
        )

        if "<body>" in content:
            content = content.replace("<body>", f"<body>\n{upload_ui}")
        elif "<BODY>" in content:
            content = content.replace("<BODY>", f"<BODY>\n{upload_ui}")

        enc = content.encode("utf-8", errors="replace")
        encoded_f = io.BytesIO()
        encoded_f.write(enc)
        encoded_f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(enc)))
        self.end_headers()
        return encoded_f

@register
class HttpServerTool(Tool):
    id = "network.http_server"
    name = "Servidor Web Local e Compartilhamento"
    category = "Rede e Internet"
    description = "Compartilhe pastas na rede local com servidor HTTP embutido e QR Code para celular"
    keywords = ["http", "servidor", "compartilhar", "arquivos", "rede", "transferencia", "qr", "web", "lan"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HttpServerView(self, parent)

class HttpServerView(QWidget):
    def __init__(self, tool: HttpServerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._shared_dir: Path = Path.home() / "Downloads"

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

        # Configurações do Servidor
        card_cfg = QFrame()
        card_cfg.setProperty("class", "card")
        l_cfg = QVBoxLayout(card_cfg)
        l_cfg.setContentsMargins(14, 12, 14, 12)
        l_cfg.setSpacing(10)

        # Linha 1: Pasta Compartilhada
        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("Pasta a Compartilhar:"))
        self.txt_dir = QLineEdit(str(self._shared_dir))
        self.txt_dir.setReadOnly(True)
        row_dir.addWidget(self.txt_dir, stretch=1)

        self.btn_select_dir = QPushButton("Selecionar Pasta...")
        self.btn_select_dir.clicked.connect(self._select_dir)
        row_dir.addWidget(self.btn_select_dir)
        l_cfg.addLayout(row_dir)

        # Linha 2: Porta e Controle
        row_ctrl = QHBoxLayout()
        row_ctrl.addWidget(QLabel("Porta TCP:"))
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(8000)
        row_ctrl.addWidget(self.spin_port)

        row_ctrl.addSpacing(20)

        self.btn_toggle = QPushButton("Iniciar Servidor Local")
        self.btn_toggle.setProperty("class", "primary")
        self.btn_toggle.clicked.connect(self._toggle_server)
        row_ctrl.addWidget(self.btn_toggle)

        self.btn_open_browser = QPushButton("Abrir no Navegador")
        self.btn_open_browser.setEnabled(False)
        self.btn_open_browser.clicked.connect(self._open_in_browser)
        row_ctrl.addWidget(self.btn_open_browser)

        row_ctrl.addStretch()
        l_cfg.addLayout(row_ctrl)

        layout.addWidget(card_cfg)

        # Seção do QR Code e URL Ativa
        card_status = QFrame()
        card_status.setProperty("class", "card")
        l_stat = QHBoxLayout(card_status)
        l_stat.setContentsMargins(14, 14, 14, 14)
        l_stat.setSpacing(20)

        self.lbl_qr = QLabel("Inicie o servidor para gerar o QR Code.")
        self.lbl_qr.setFixedSize(160, 160)
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        self.lbl_qr.setStyleSheet("background: #1a1a1a; border-radius: 4px; border: 1px dashed #444;")
        l_stat.addWidget(self.lbl_qr)

        l_info = QVBoxLayout()
        l_info.setSpacing(6)
        self.lbl_url_status = QLabel("Status: Servidor Parado")
        self.lbl_url_status.setStyleSheet("font-size: 15px; font-weight: 600;")
        l_info.addWidget(self.lbl_url_status)

        self.lbl_instructions = QLabel(
            "Dispositivos na mesma rede Wi-Fi podem acessar os arquivos da pasta\n"
            "digitando o endereço acima no navegador ou simplesmente escaneando\n"
            "o QR Code com a câmera do smartphone."
        )
        self.lbl_instructions.setProperty("class", "secondary")
        l_info.addWidget(self.lbl_instructions)
        l_info.addStretch()

        l_stat.addLayout(l_info, stretch=1)
        layout.addWidget(card_status)

        # Painel de Log de Acessos
        self.log_panel = LogPanelWidget()
        layout.addWidget(self.log_panel)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _select_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Compartilhar", str(self._shared_dir))
        if folder:
            self._shared_dir = Path(folder)
            self.txt_dir.setText(str(self._shared_dir))

    def _toggle_server(self):
        if self._server is None:
            self._start_server()
        else:
            self._stop_server()

    def _start_server(self):
        port = self.spin_port.value()
        host = "0.0.0.0"
        local_ip = get_primary_local_ip()
        url = f"http://{local_ip}:{port}/"

        handler_factory = functools.partial(
            LoggingHTTPRequestHandler,
            log_callback=self.log_panel.append_log,
            directory=str(self._shared_dir)
        )

        try:
            self._server = HTTPServer((host, port), handler_factory)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível iniciar o servidor na porta {port}:\n{str(e)}")
            return

        def serve():
            self._server.serve_forever()

        self._server_thread = threading.Thread(target=serve, daemon=True)
        self._server_thread.start()

        self.btn_toggle.setText("Parar Servidor")
        self.btn_select_dir.setEnabled(False)
        self.spin_port.setEnabled(False)
        self.btn_open_browser.setEnabled(True)
        self._active_url = url

        self.lbl_url_status.setText(f"Online: {url}")
        self.lbl_url_status.setStyleSheet("font-size: 16px; font-weight: 700; color: #10b981;")
        self.log_panel.append_log("INFO", f"Servidor iniciado compartilhando '{self._shared_dir}' em {url}")

        # Gera QR Code da URL
        self._render_qr(url)

    def _stop_server(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._server_thread = None

        self.btn_toggle.setText("Iniciar Servidor Local")
        self.btn_select_dir.setEnabled(True)
        self.spin_port.setEnabled(True)
        self.btn_open_browser.setEnabled(False)

        self.lbl_url_status.setText("Status: Servidor Parado")
        self.lbl_url_status.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.lbl_qr.setText("Inicie o servidor para gerar o QR Code.")
        self.lbl_qr.setPixmap(QPixmap())
        self.log_panel.append_log("INFO", "Servidor HTTP finalizado.")

    def _render_qr(self, text: str):
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.size[0], img.size[1], QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_qr.setPixmap(pix.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _open_in_browser(self):
        if hasattr(self, "_active_url"):
            QDesktopServices.openUrl(QUrl(self._active_url))

    def hideEvent(self, event):
        super().hideEvent(event)
