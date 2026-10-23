"""
Lógica pura da ferramenta Servidor HTTP Local e Compartilhamento de Arquivos.
Manipulador HTTP com upload multipart, descoberta de IP local e geração de QR code sem Qt.
"""
import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
import io
import os
from pathlib import Path
import socket
import threading
from typing import Callable, Optional
from PIL import Image
import qrcode


def get_primary_local_ip() -> str:
    """Descobre o endereço IPv4 principal da máquina na rede local."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
        """Recebe upload de arquivos vindos de celulares ou outros dispositivos na LAN."""
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


def generate_qr_image(text: str) -> Image.Image:
    """Gera o objeto PIL Image do QR code correspondente a uma URL."""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")
