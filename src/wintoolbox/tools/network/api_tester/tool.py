"""
Ferramenta: Testador de API HTTP (Mini Postman).
Execução de requisições GET, POST, PUT, DELETE com inspeção de headers e JSON.
"""
import time
import json
import urllib.request
import urllib.error
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner

@register
class ApiTesterTool(Tool):
    id = "network.api_tester"
    name = "Testador de API (Mini Postman)"
    category = "Rede e Internet"
    description = "Envio de requisições HTTP (GET, POST, PUT, DELETE), cabeçalhos customizados e inspeção de respostas"
    keywords = ["api", "postman", "http", "rest", "json", "endpoint", "requisicao", "headers", "get", "post"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ApiTesterView(self, parent)

class ApiTesterView(QWidget):
    def __init__(self, tool: ApiTesterTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
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

        # Barra de Requisição (Método + URL + Botão Enviar)
        req_card = QFrame()
        req_card.setProperty("class", "card")
        l_req = QHBoxLayout(req_card)
        l_req.setContentsMargins(10, 10, 10, 10)
        l_req.setSpacing(8)

        self.cmb_method = QComboBox()
        self.cmb_method.addItems(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
        self.cmb_method.setFixedWidth(90)
        l_req.addWidget(self.cmb_method)

        self.txt_url = QLineEdit("https://httpbin.org/get")
        self.txt_url.setPlaceholderText("https://exemplo.com/api/v1/recurso")
        l_req.addWidget(self.txt_url, stretch=1)

        self.btn_send = QPushButton("Enviar Requisição")
        self.btn_send.setProperty("class", "primary")
        self.btn_send.clicked.connect(self._send_request)
        l_req.addWidget(self.btn_send)

        layout.addWidget(req_card)

        # Abas de Parâmetros de Entrada (Headers e Body)
        tabs_in = QTabWidget()
        tabs_in.setFixedHeight(160)

        # Aba Headers
        self.txt_headers = QPlainTextEdit("Content-Type: application/json\nUser-Agent: WinToolbox/1.0")
        self.txt_headers.setFont(QFont("Cascadia Mono, Consolas", 9))
        tabs_in.addTab(self.txt_headers, "Cabeçalhos (Headers - Linha por linha 'Chave: Valor')")

        # Aba Body
        self.txt_body = QPlainTextEdit('{\n  "mensagem": "teste"\n}')
        self.txt_body.setFont(QFont("Cascadia Mono, Consolas", 9))
        tabs_in.addTab(self.txt_body, "Corpo da Requisição (Body - JSON / Texto)")

        layout.addWidget(tabs_in)

        # Status da Resposta
        row_status = QHBoxLayout()
        self.lbl_resp_status = QLabel("Status: Aguardando requisição")
        self.lbl_resp_status.setStyleSheet("font-size: 14px; font-weight: 600;")
        row_status.addWidget(self.lbl_resp_status)

        self.lbl_resp_time = QLabel("")
        self.lbl_resp_time.setProperty("class", "secondary")
        row_status.addWidget(self.lbl_resp_time)

        row_status.addStretch()

        btn_copy_resp = QPushButton("Copiar Resposta")
        btn_copy_resp.clicked.connect(self._copy_response)
        row_status.addWidget(btn_copy_resp)
        layout.addLayout(row_status)

        # Abas de Exibição da Resposta
        tabs_out = QTabWidget()

        # Resposta Formatada
        self.txt_response = QPlainTextEdit()
        self.txt_response.setReadOnly(True)
        self.txt_response.setFont(QFont("Cascadia Mono, Consolas", 9))
        tabs_out.addTab(self.txt_response, "Corpo da Resposta")

        # Headers de Resposta
        self.table_resp_headers = QTableWidget(0, 2)
        self.table_resp_headers.setHorizontalHeaderLabels(["Cabeçalho", "Valor"])
        self.table_resp_headers.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_resp_headers.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_resp_headers.verticalHeader().setVisible(False)
        tabs_out.addTab(self.table_resp_headers, "Cabeçalhos de Resposta (Headers)")

        layout.addWidget(tabs_out)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _send_request(self):
        url = self.txt_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Aviso", "Informe a URL da requisição.")
            return

        method = self.cmb_method.currentText()
        headers_str = self.txt_headers.toPlainText()
        body_str = self.txt_body.toPlainText().strip() if method in ("POST", "PUT", "PATCH") else None

        # Parse de headers
        headers_dict = {}
        for line in headers_str.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                headers_dict[k.strip()] = v.strip()

        self.btn_send.setEnabled(False)
        self.lbl_resp_status.setText("Enviando requisição...")
        self.lbl_resp_status.setStyleSheet("font-size: 14px; font-weight: 600; color: #aaaaaa;")

        def worker(ctx):
            t0 = time.time()
            data_bytes = body_str.encode("utf-8") if body_str else None
            req = urllib.request.Request(url, data=data_bytes, headers=headers_dict, method=method)

            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    elapsed = (time.time() - t0) * 1000
                    raw_content = resp.read()
                    text = raw_content.decode("utf-8", errors="replace")
                    resp_headers = dict(resp.getheaders())
                    return {
                        "code": resp.getcode(),
                        "time_ms": elapsed,
                        "size": len(raw_content),
                        "headers": resp_headers,
                        "body": text,
                        "error": None
                    }
            except urllib.error.HTTPError as e:
                elapsed = (time.time() - t0) * 1000
                raw = e.read()
                return {
                    "code": e.code,
                    "time_ms": elapsed,
                    "size": len(raw),
                    "headers": dict(e.headers.items()) if e.headers else {},
                    "body": raw.decode("utf-8", errors="replace"),
                    "error": str(e.reason)
                }
            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                return {
                    "code": 0,
                    "time_ms": elapsed,
                    "size": 0,
                    "headers": {},
                    "body": f"Erro de conexão: {str(e)}",
                    "error": str(e)
                }

        def on_done(res):
            self.btn_send.setEnabled(True)
            code = res["code"]
            time_ms = res["time_ms"]
            size_kb = res["size"] / 1024

            if code >= 200 and code < 300:
                color = "#10b981"  # Verde
            elif code >= 300 and code < 400:
                color = "#f59e0b"  # Amarelo
            else:
                color = "#ef4444"  # Vermelho

            self.lbl_resp_status.setText(f"Status: {code} {'OK' if code==200 else ''}")
            self.lbl_resp_status.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {color};")
            self.lbl_resp_time.setText(f"Tempo: {time_ms:.0f} ms | Tamanho: {size_kb:.2f} KB")

            # Formata JSON se possível
            body_text = res["body"]
            try:
                parsed = json.loads(body_text)
                body_text = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass
            self.txt_response.setPlainText(body_text)

            # Preenche tabela de headers
            headers = res["headers"]
            self.table_resp_headers.setRowCount(len(headers))
            for row, (hk, hv) in enumerate(headers.items()):
                self.table_resp_headers.setItem(row, 0, QTableWidgetItem(hk))
                self.table_resp_headers.setItem(row, 1, QTableWidgetItem(hv))

        self.runner.start_task(worker, on_finished=on_done)

    def _copy_response(self):
        text = self.txt_response.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", "Corpo da resposta copiado para a área de transferência.")
