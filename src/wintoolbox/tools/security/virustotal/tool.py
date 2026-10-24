"""
Interface gráfica do Consultor de Reputação e Hashes no VirusTotal.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.security.virustotal.logic import (
    calculate_file_sha256, query_virustotal_hash
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("security.virustotal.ui")


@register
class VirusTotalTool(Tool):
    id = "security.virustotal"
    name = "Consulta de Ameaças no VirusTotal"
    category = "Segurança"
    description = "Consulta de reputação de arquivos e hashes em dezenas de motores antivírus via API oficial do VirusTotal"
    keywords = ["virustotal", "antivirus", "malware", "hash", "sha256", "reputacao", "seguranca", "ameaca"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return VirusTotalView(self, parent)


class VirusTotalView(QWidget):
    def __init__(self, tool: VirusTotalTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Barra de seleção de arquivo ou digitação de hash
        input_card = QFrame()
        input_card.setObjectName("Card")
        in_lay = QVBoxLayout(input_card)
        in_lay.setContentsMargins(14, 14, 14, 14)
        in_lay.setSpacing(10)

        in_lay.addWidget(QLabel("Selecione um arquivo local para calcular o hash ou digite o hash (MD5, SHA-1, SHA-256):"))

        row = QHBoxLayout()
        self.txt_hash = QLineEdit()
        self.txt_hash.setPlaceholderText("Ex: 275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f")
        self.txt_hash.returnPressed.connect(self._query_async)
        row.addWidget(self.txt_hash, stretch=1)

        btn_browse = QPushButton("Arquivo Local...")
        btn_browse.clicked.connect(self._browse_file)
        row.addWidget(btn_browse)

        self.btn_query = QPushButton("Consultar no VirusTotal")
        self.btn_query.setProperty("accent", True)
        self.btn_query.clicked.connect(self._query_async)
        row.addWidget(self.btn_query)

        in_lay.addLayout(row)
        layout.addWidget(input_card)

        # Painel de Resumo / Detecções
        self.summary_card = QFrame()
        self.summary_card.setObjectName("Card")
        s_lay = QHBoxLayout(self.summary_card)
        s_lay.setContentsMargins(16, 16, 16, 16)

        self.lbl_score = QLabel("0 / 0")
        self.lbl_score.setStyleSheet("font-size: 26px; font-weight: bold; color: #888888;")
        s_lay.addWidget(self.lbl_score)

        self.lbl_summary_text = QLabel("Aguardando consulta de arquivo ou hash.")
        self.lbl_summary_text.setStyleSheet("font-size: 13px;")
        self.lbl_summary_text.setWordWrap(True)
        s_lay.addWidget(self.lbl_summary_text, stretch=1)

        layout.addWidget(self.summary_card)

        # Tabela com as detecções dos motores antivírus
        layout.addWidget(QLabel("Motores Antivírus com Detecção Positiva:"))
        self.table_detections = QTableWidget(0, 3)
        self.table_detections.setHorizontalHeaderLabels(["Motor Antivírus", "Categoria", "Identificação da Ameaça"])
        self.table_detections.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_detections.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_detections.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.table_detections, stretch=1)

    def _browse_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Calcular Hash", "", "Todos os Arquivos (*.*)")
        if p:
            try:
                sha = calculate_file_sha256(Path(p))
                self.txt_hash.setText(sha)
                show_toast(self, "Hash SHA-256 calculado com sucesso!")
            except Exception as exc:
                show_toast(self, f"Erro ao calcular hash: {exc}", is_error=True)

    def _query_async(self) -> None:
        h = self.txt_hash.text().strip()
        if not h:
            show_toast(self, "Informe um hash para consulta.", is_error=True)
            return

        self.btn_query.setEnabled(False)
        self.lbl_summary_text.setText("Consultando relatório na API v3 do VirusTotal...")

        def _worker():
            return query_virustotal_hash(h)

        def _on_done(res: Dict[str, Any]):
            self.btn_query.setEnabled(True)

            if "error" in res:
                self.lbl_score.setText("Erro")
                self.lbl_score.setStyleSheet("font-size: 22px; font-weight: bold; color: #d83b01;")
                self.lbl_summary_text.setText(res["error"])
                self.table_detections.setRowCount(0)
                show_toast(self, "Aviso na consulta VirusTotal", is_error=True)
                return

            if res.get("not_found"):
                self.lbl_score.setText("0 / 0")
                self.lbl_score.setStyleSheet("font-size: 22px; font-weight: bold; color: #888888;")
                self.lbl_summary_text.setText(res.get("message", "Hash não encontrado na base de dados."))
                self.table_detections.setRowCount(0)
                return

            mal = res.get("malicious", 0)
            total = res.get("total_engines", 0)
            self.lbl_score.setText(f"{mal} / {total}")

            if mal > 0:
                self.lbl_score.setStyleSheet("font-size: 26px; font-weight: bold; color: #d83b01;")
                self.lbl_summary_text.setText(
                    f"Ameaça detectada por {mal} motor(es) antivírus!\n"
                    f"Nome comum: {res.get('meaningful_name')} | Reputação na comunidade: {res.get('reputation')}"
                )
            else:
                self.lbl_score.setStyleSheet("font-size: 26px; font-weight: bold; color: #107c41;")
                self.lbl_summary_text.setText(
                    f"Arquivo limpo: 0 detecções em {total} motores antivírus.\n"
                    f"Nome comum: {res.get('meaningful_name')}"
                )

            # Preenche tabela de detecções
            dets = res.get("detections", [])
            self.table_detections.setRowCount(len(dets))
            for row, d in enumerate(dets):
                self.table_detections.setItem(row, 0, QTableWidgetItem(d["engine"]))
                self.table_detections.setItem(row, 1, QTableWidgetItem(d["category"]))
                self.table_detections.setItem(row, 2, QTableWidgetItem(d["result"]))

        def _on_error(err):
            self.btn_query.setEnabled(True)
            self.lbl_summary_text.setText(f"Erro na requisição: {err}")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
