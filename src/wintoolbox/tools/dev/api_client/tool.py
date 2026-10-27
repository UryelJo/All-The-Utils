"""
Interface gráfica do Cliente HTTP / REST de Desenvolvedor (dev.api_client).
Permite testar APIs com métodos GET, POST, PUT, DELETE, PATCH, inspecionar headers,
enviar payloads JSON e analisar respostas formatadas em tempo real.
"""
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.dev.api_client.logic import execute_http_request
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class ApiClientTool(Tool):
    id = "dev.api_client"
    name = "Cliente HTTP / REST para Desenvolvedores"
    category = "Desenvolvedores"
    description = (
        "Cliente de requisições HTTP e REST completo para testar APIs locais e externas, "
        "com suporte a headers customizados, body JSON, medição de latência e formatação de respostas."
    )
    keywords = ["http", "rest", "api", "client", "postman", "curl", "get", "post", "json", "headers"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ApiClientView(self, parent)


class ApiClientView(QWidget):
    def __init__(self, tool: ApiClientTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Barra de Endereço e Ação
        addr_box = QHBoxLayout()
        self._combo_method = QComboBox()
        self._combo_method.addItems(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
        self._combo_method.setStyleSheet("font-weight: bold; padding: 4px 8px;")
        addr_box.addWidget(self._combo_method)

        self._txt_url = QLineEdit("http://localhost:8000/api")
        self._txt_url.setFont(QFont("Consolas", 10))
        self._txt_url.setPlaceholderText("https://api.exemplo.com/v1/recurso...")
        self._txt_url.returnPressed.connect(self._send_request)
        addr_box.addWidget(self._txt_url)

        self._btn_send = QPushButton("Enviar Requisição")
        self._btn_send.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self._btn_send.clicked.connect(self._send_request)
        addr_box.addWidget(self._btn_send)

        root_layout.addLayout(addr_box)

        # Splitter Vertical: Requisição em cima, Resposta embaixo
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Painel Superior: Configuração da Requisição
        req_tabs = QTabWidget()

        # Aba 1: Corpo da Requisição (Body)
        self._txt_req_body = QPlainTextEdit()
        self._txt_req_body.setFont(QFont("Consolas", 9))
        self._txt_req_body.setPlaceholderText('{\n  "nome": "Produto Teste",\n  "preco": 99.90\n}')
        req_tabs.addTab(self._txt_req_body, "Corpo (Body JSON / Texto)")

        # Aba 2: Cabeçalhos (Headers)
        self._txt_req_headers = QPlainTextEdit()
        self._txt_req_headers.setFont(QFont("Consolas", 9))
        self._txt_req_headers.setPlaceholderText("Content-Type: application/json\nAuthorization: Bearer token123\nAccept: application/json")
        req_tabs.addTab(self._txt_req_headers, "Cabeçalhos (Headers)")

        splitter.addWidget(req_tabs)

        # Painel Inferior: Resposta da API
        resp_widget = QWidget()
        resp_layout = QVBoxLayout(resp_widget)
        resp_layout.setContentsMargins(0, 0, 0, 0)
        resp_layout.setSpacing(6)

        # Barra de Status da Resposta
        status_bar = QHBoxLayout()
        self._lbl_status_badge = QLabel("Status: Pronto")
        self._lbl_status_badge.setStyleSheet("font-weight: bold; padding: 4px 8px; border-radius: 4px; background: #f3f4f6;")
        status_bar.addWidget(self._lbl_status_badge)

        self._lbl_time_badge = QLabel("Latência: -")
        self._lbl_time_badge.setStyleSheet("color: #4b5563; font-size: 11px;")
        status_bar.addWidget(self._lbl_time_badge)

        self._lbl_size_badge = QLabel("Tamanho: -")
        self._lbl_size_badge.setStyleSheet("color: #4b5563; font-size: 11px;")
        status_bar.addWidget(self._lbl_size_badge)

        status_bar.addStretch()

        btn_copy_resp = QPushButton("Copiar Resposta")
        btn_copy_resp.clicked.connect(self._copy_response)
        status_bar.addWidget(btn_copy_resp)

        resp_layout.addLayout(status_bar)

        # Abas de Resposta
        self._resp_tabs = QTabWidget()

        # Aba Corpo da Resposta
        self._txt_resp_body = QPlainTextEdit()
        self._txt_resp_body.setFont(QFont("Consolas", 9))
        self._txt_resp_body.setReadOnly(True)
        self._resp_tabs.addTab(self._txt_resp_body, "Corpo da Resposta")

        # Aba Cabeçalhos da Resposta
        cols = [
            Column("key", "Cabeçalho", width=220),
            Column("value", "Valor", width=420),
        ]
        self._headers_table = DataTableView(cols, key="key", parent=self)
        self._resp_tabs.addTab(self._headers_table, "Cabeçalhos Retornados")

        resp_layout.addWidget(self._resp_tabs)
        splitter.addWidget(resp_widget)

        splitter.setSizes([180, 280])
        root_layout.addWidget(splitter)

    def _parse_headers_input(self) -> Dict[str, str]:
        raw = self._txt_req_headers.toPlainText().strip()
        headers: Dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        return headers

    def _send_request(self):
        url = self._txt_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Aviso", "Por favor, digite a URL da requisição.")
            return

        method = self._combo_method.currentText()
        headers = self._parse_headers_input()
        body = self._txt_req_body.toPlainText().strip() or None

        self._lbl_status_badge.setText("Enviando...")
        self._lbl_status_badge.setStyleSheet("background: #fef3c7; color: #92400e; font-weight: bold; padding: 4px 8px;")
        self._btn_send.setEnabled(False)

        self._runner.run(
            execute_http_request,
            url,
            method=method,
            headers=headers,
            body=body,
            on_success=self._on_request_success,
            on_error=self._on_request_error,
        )

    def _on_request_success(self, res: dict):
        self._btn_send.setEnabled(True)
        code = res.get("status_code", 0)
        reason = res.get("status_text", "")
        ms = res.get("elapsed_ms", 0.0)
        bytes_len = res.get("body_bytes", 0)

        # Status Badge
        badge_text = f"Status: {code} {reason}"
        if 200 <= code < 300:
            style = "background: #d1fae5; color: #065f46; border: 1px solid #10b981; font-weight: bold; padding: 4px 8px;"
        elif 300 <= code < 400:
            style = "background: #e0f2fe; color: #0369a1; border: 1px solid #38bdf8; font-weight: bold; padding: 4px 8px;"
        else:
            style = "background: #fee2e2; color: #991b1b; border: 1px solid #ef4444; font-weight: bold; padding: 4px 8px;"

        self._lbl_status_badge.setText(badge_text)
        self._lbl_status_badge.setStyleSheet(style)

        self._lbl_time_badge.setText(f"Latência: {ms:.1f} ms")
        self._lbl_size_badge.setText(f"Tamanho: {bytes_len / 1024:.2f} KB ({bytes_len} bytes)")

        # Corpo e Headers
        self._txt_resp_body.setPlainText(res.get("body", ""))
        resp_headers = res.get("headers", {})
        header_records = [{"key": k, "value": v} for k, v in resp_headers.items()]
        self._headers_table.set_records(header_records)

    def _on_request_error(self, exc: Exception):
        self._btn_send.setEnabled(True)
        self._lbl_status_badge.setText("Erro de Rede")
        self._lbl_status_badge.setStyleSheet("background: #fee2e2; color: #991b1b; padding: 4px 8px; font-weight: bold;")
        self._txt_resp_body.setPlainText(f"Falha ao executar requisição: {exc}")

    def _copy_response(self):
        txt = self._txt_resp_body.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
