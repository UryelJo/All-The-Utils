"""
Interface de usuário para a ferramenta Servidor HTTP Mock Local.
"""
from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.mock_server.logic import (
    MockHttpServer,
    MockRoute,
    RequestLogEntry,
)


@register
class MockServerTool(Tool):
    """Servidor web mock local embutido para testes de integração e endpoints de APIs."""

    id = "dev.mock_server"
    name = "Servidor HTTP Mock Local"
    description = "Servidor web embutido para testes de APIs locais com rotas mockadas, latência simulada e inspeção de requisições."
    category = "Desenvolvimento"

    def __init__(self):
        super().__init__()
        self.server = MockHttpServer()
        self.routes: List[MockRoute] = [
            MockRoute(path="/api/health", method="GET", status_code=200, body='{"status": "healthy", "service": "mock-api"}'),
            MockRoute(path="/api/users", method="GET", status_code=200, body='[{"id": 1, "name": "Ana Silva"}, {"id": 2, "name": "Carlos Lima"}]'),
            MockRoute(path="/api/login", method="POST", status_code=200, body='{"token": "mock-jwt-token-xyz123"}'),
        ]

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Servidor HTTP Mock Local")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Suba um servidor HTTP em localhost em segundos. Configure payloads de resposta JSON, "
            "códigos de erro, simule lentidão de rede e monitore chamadas de clientes."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Barra de Controle do Servidor
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ctrl_layout = QHBoxLayout(ctrl_frame)

        ctrl_layout.addWidget(QLabel("Porta HTTP:"))
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(8080)
        ctrl_layout.addWidget(self.spin_port)

        self.btn_toggle = QPushButton("▶ Iniciar Servidor")
        self.btn_toggle.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white;")
        self.btn_toggle.clicked.connect(self._toggle_server)
        ctrl_layout.addWidget(self.btn_toggle)

        self.lbl_status = QLabel("● Parado")
        self.lbl_status.setStyleSheet("color: #888888; font-weight: bold;")
        ctrl_layout.addWidget(self.lbl_status)
        ctrl_layout.addStretch()

        layout.addWidget(ctrl_frame)

        # Splitter: Rotas e Logs
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Painel de Rotas
        w_routes = QWidget()
        v_routes = QVBoxLayout(w_routes)
        v_routes.setContentsMargins(0, 0, 0, 0)

        h_r_head = QHBoxLayout()
        h_r_head.addWidget(QLabel("Rotas e Respostas Configuradas:"))
        btn_add_route = QPushButton("+ Adicionar Nova Rota")
        btn_add_route.clicked.connect(self._add_route_dialog)
        btn_del_route = QPushButton("Remover Rota Selecionada")
        btn_del_route.clicked.connect(self._del_route)
        h_r_head.addStretch()
        h_r_head.addWidget(btn_add_route)
        h_r_head.addWidget(btn_del_route)
        v_routes.addLayout(h_r_head)

        self.table_routes = QTableWidget()
        self.table_routes.setColumnCount(5)
        self.table_routes.setHorizontalHeaderLabels([
            "Método", "Caminho (Path)", "Status HTTP", "Delay (ms)", "Corpo da Resposta (Preview)"
        ])
        self.table_routes.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_routes.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v_routes.addWidget(self.table_routes)
        splitter.addWidget(w_routes)

        # Painel de Logs de Requisições
        w_logs = QWidget()
        v_logs = QVBoxLayout(w_logs)
        v_logs.setContentsMargins(0, 0, 0, 0)

        h_l_head = QHBoxLayout()
        h_l_head.addWidget(QLabel("Log de Requisições Recebidas em Tempo Real:"))
        btn_clear_logs = QPushButton("Limpar Logs")
        btn_clear_logs.clicked.connect(self._clear_logs)
        h_l_head.addStretch()
        h_l_head.addWidget(btn_clear_logs)
        v_logs.addLayout(h_l_head)

        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(5)
        self.table_logs.setHorizontalHeaderLabels(["Horário", "IP Origem", "Método", "Endpoint", "Status"])
        self.table_logs.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        v_logs.addWidget(self.table_logs)
        splitter.addWidget(w_logs)

        layout.addWidget(splitter, 1)

        self._populate_routes()
        self.server.log_listener = self._on_log_received
        return widget

    def _toggle_server(self):
        if not self.server.is_running:
            port = self.spin_port.value()
            try:
                actual_port = self.server.start(port=port, routes=self.routes)
                self.btn_toggle.setText("■ Parar Servidor")
                self.btn_toggle.setStyleSheet("font-weight: bold; background-color: #d32f2f; color: white;")
                self.lbl_status.setText(f"● Executando em http://127.0.0.1:{actual_port}")
                self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")
                self.spin_port.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao iniciar servidor mock: {e}")
        else:
            self.server.stop()
            self.btn_toggle.setText("▶ Iniciar Servidor")
            self.btn_toggle.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white;")
            self.lbl_status.setText("● Parado")
            self.lbl_status.setStyleSheet("color: #888888; font-weight: bold;")
            self.spin_port.setEnabled(True)

    def _populate_routes(self):
        self.table_routes.setRowCount(len(self.routes))
        for r, route in enumerate(self.routes):
            self.table_routes.setItem(r, 0, QTableWidgetItem(route.method))
            self.table_routes.setItem(r, 1, QTableWidgetItem(route.path))
            self.table_routes.setItem(r, 2, QTableWidgetItem(str(route.status_code)))
            self.table_routes.setItem(r, 3, QTableWidgetItem(f"{route.delay_ms} ms"))
            self.table_routes.setItem(r, 4, QTableWidgetItem(route.body[:80]))
        self.server.set_routes(self.routes)

    def _add_route_dialog(self):
        dlg = QDialog()
        dlg.setWindowTitle("Adicionar Rota Mock")
        dlg.resize(500, 400)
        v = QVBoxLayout(dlg)

        grid = QGridLayout()
        grid.addWidget(QLabel("Método:"), 0, 0)
        c_method = QComboBox()
        c_method.addItems(["GET", "POST", "PUT", "DELETE", "PATCH", "ALL"])
        grid.addWidget(c_method, 0, 1)

        grid.addWidget(QLabel("Caminho (Path):"), 1, 0)
        t_path = QLineEdit("/api/novo")
        grid.addWidget(t_path, 1, 1)

        grid.addWidget(QLabel("Código HTTP:"), 2, 0)
        s_code = QSpinBox()
        s_code.setRange(100, 599)
        s_code.setValue(200)
        grid.addWidget(s_code, 2, 1)

        grid.addWidget(QLabel("Simular Latência:"), 3, 0)
        s_delay = QSpinBox()
        s_delay.setRange(0, 10000)
        s_delay.setValue(0)
        s_delay.setSuffix(" ms")
        grid.addWidget(s_delay, 3, 1)

        v.addLayout(grid)
        v.addWidget(QLabel("Corpo da Resposta (Payload JSON/Texto):"))
        t_body = QTextEdit('{"message": "sucesso"}')
        v.addWidget(t_body)

        btns = QHBoxLayout()
        b_ok = QPushButton("Adicionar")
        b_ok.clicked.connect(dlg.accept)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(dlg.reject)
        btns.addStretch()
        btns.addWidget(b_ok)
        btns.addWidget(b_cancel)
        v.addLayout(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_r = MockRoute(
                path=t_path.text().strip(),
                method=c_method.currentText(),
                status_code=s_code.value(),
                delay_ms=s_delay.value(),
                body=t_body.toPlainText()
            )
            self.routes.append(new_r)
            self._populate_routes()

    def _del_route(self):
        row = self.table_routes.currentRow()
        if 0 <= row < len(self.routes):
            self.routes.pop(row)
            self._populate_routes()

    def _on_log_received(self, entry: RequestLogEntry):
        # Chamado na thread do servidor; insere na tabela
        row = self.table_logs.rowCount()
        self.table_logs.insertRow(row)
        self.table_logs.setItem(row, 0, QTableWidgetItem(entry.timestamp))
        self.table_logs.setItem(row, 1, QTableWidgetItem(entry.client_ip))
        self.table_logs.setItem(row, 2, QTableWidgetItem(entry.method))
        self.table_logs.setItem(row, 3, QTableWidgetItem(entry.path))

        status_item = QTableWidgetItem(str(entry.status_code))
        if entry.status_code < 400:
            status_item.setForeground(QColor(76, 175, 80))
        else:
            status_item.setForeground(QColor(244, 67, 54))
        self.table_logs.setItem(row, 4, status_item)
        self.table_logs.scrollToBottom()

    def _clear_logs(self):
        self.table_logs.setRowCount(0)
