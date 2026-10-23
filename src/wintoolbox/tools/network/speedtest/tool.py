"""
Ferramenta: Teste de Velocidade de Conexão à Internet (speedtest-cli).
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.speedtest.logic import run_speedtest

@register
class SpeedtestTool(Tool):
    id = "network.speedtest"
    name = "Teste de Velocidade de Internet"
    category = "Rede e Internet"
    description = "Mede ping, taxa de download e upload da conexão utilizando speedtest-cli"
    keywords = ["velocidade", "speedtest", "download", "upload", "ping", "latencia", "banda", "rede", "internet"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SpeedtestView(self, parent)

class SpeedtestView(QWidget):
    def __init__(self, tool: SpeedtestTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.last_result = None
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
        layout.setSpacing(16)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Barra de Ações do Teste
        bar_actions = QHBoxLayout()
        self.btn_start = QPushButton("Iniciar Teste de Velocidade")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self._start_test)
        bar_actions.addWidget(self.btn_start)

        self.btn_copy = QPushButton("Copiar Resultados")
        self.btn_copy.setFixedHeight(36)
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_results)
        bar_actions.addWidget(self.btn_copy)
        bar_actions.addStretch()
        layout.addLayout(bar_actions)

        # Barra de Progresso e Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Pronto para iniciar o teste.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Grid de Métricas Principais (Ping, Download, Upload)
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        # Card Ping
        self.card_ping, self.val_ping = self._create_metric_card("LATÊNCIA (PING)", "--", "ms")
        metrics_layout.addWidget(self.card_ping)

        # Card Download
        self.card_dl, self.val_dl = self._create_metric_card("DOWNLOAD", "--", "Mbps")
        metrics_layout.addWidget(self.card_dl)

        # Card Upload
        self.card_ul, self.val_ul = self._create_metric_card("UPLOAD", "--", "Mbps")
        metrics_layout.addWidget(self.card_ul)

        layout.addLayout(metrics_layout)

        # Card Detalhes da Conexão
        card_details = QFrame()
        card_details.setProperty("class", "card")
        l_det = QVBoxLayout(card_details)
        l_det.setSpacing(8)

        lbl_det_title = QLabel("Detalhes do Provedor e Roteamento")
        lbl_det_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        l_det.addWidget(lbl_det_title)

        self.lbl_server = QLabel("Servidor: --")
        l_det.addWidget(self.lbl_server)

        self.lbl_isp = QLabel("Provedor (ISP): --")
        l_det.addWidget(self.lbl_isp)

        self.lbl_ip = QLabel("IP Público Detectado: --")
        l_det.addWidget(self.lbl_ip)

        layout.addWidget(card_details)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _create_metric_card(self, title: str, initial_val: str, unit: str):
        card = QFrame()
        card.setProperty("class", "card")
        l = QVBoxLayout(card)
        l.setSpacing(4)
        l.setContentsMargins(16, 16, 16, 16)

        lbl_t = QLabel(title)
        lbl_t.setProperty("class", "secondary")
        lbl_t.setStyleSheet("font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        l.addWidget(lbl_t)

        val_row = QHBoxLayout()
        val_lbl = QLabel(initial_val)
        val_lbl.setStyleSheet("font-size: 26px; font-weight: 700; color: #0067c0;")
        val_row.addWidget(val_lbl)

        lbl_u = QLabel(unit)
        lbl_u.setProperty("class", "secondary")
        lbl_u.setStyleSheet("font-size: 13px; font-weight: 500; margin-bottom: 4px;")
        val_row.addWidget(lbl_u, alignment=Qt.AlignBottom)
        val_row.addStretch()

        l.addLayout(val_row)
        return card, val_lbl

    def _start_test(self):
        self.btn_start.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.progress_bar.setValue(5)
        self.lbl_status.setText("Iniciando rotina de teste...")
        self.val_ping.setText("--")
        self.val_dl.setText("--")
        self.val_ul.setText("--")
        self.lbl_server.setText("Servidor: Localizando...")
        self.lbl_isp.setText("Provedor (ISP): --")
        self.lbl_ip.setText("IP Público Detectado: --")

        def worker(ctx):
            def on_progress(msg: str, percent: int):
                ctx.send_progress(percent, msg)

            return run_speedtest(on_progress)

        def on_task_progress(percent: int, msg: str):
            self.progress_bar.setValue(percent)
            self.lbl_status.setText(msg)

        def on_finished(res):
            self.btn_start.setEnabled(True)
            self.btn_copy.setEnabled(True)
            self.last_result = res
            self.progress_bar.setValue(100)

            if not res.get("success", False):
                self.lbl_status.setText("O teste falhou ou foi interrompido.")
                QMessageBox.critical(self, "Falha no Teste", res.get("error", "Erro desconhecido."))
                return

            self.val_ping.setText(str(res["ping_ms"]))
            self.val_dl.setText(str(res["download_mbps"]))
            self.val_ul.setText(str(res["upload_mbps"]) if res["upload_mbps"] > 0 else "N/A")
            self.lbl_server.setText(f"Servidor: {res['server']}")
            self.lbl_isp.setText(f"Provedor (ISP): {res['isp']}")
            self.lbl_ip.setText(f"IP Público Detectado: {res['ip']}")
            self.lbl_status.setText("Teste concluído com sucesso!")

        def on_error(err):
            self.btn_start.setEnabled(True)
            self.lbl_status.setText("Erro ao executar teste de velocidade.")
            QMessageBox.critical(self, "Erro", f"Falha ao executar teste:\n{err}")

        self.runner.start_task(
            worker,
            on_progress=on_task_progress,
            on_finished=on_finished,
            on_error=on_error
        )

    def _copy_results(self):
        if not self.last_result:
            return
        r = self.last_result
        text = (
            f"=== Resultado do Teste de Velocidade (WinToolbox) ===\n"
            f"Ping: {r['ping_ms']} ms\n"
            f"Download: {r['download_mbps']} Mbps\n"
            f"Upload: {r['upload_mbps']} Mbps\n"
            f"Servidor: {r['server']}\n"
            f"Provedor: {r['isp']}\n"
            f"IP: {r['ip']}\n"
        )
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copiado", "Resultados copiados para a área de transferência!")
