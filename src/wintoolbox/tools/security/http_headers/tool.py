"""
Interface gráfica do Auditor de Cabeçalhos HTTP de Segurança.

Permite auditoria defensiva de conformidade de cabeçalhos HTTP para diagnóstico
da postura de segurança do próprio site/domínio do usuário.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QTextEdit,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.security.http_headers.logic import (
    HeaderAuditResult, audit_http_headers
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("security.http_headers.ui")

COLUMNS = [
    Column("header", "Cabeçalho HTTP", width=210, tooltip=True),
    Column("status", "Status", width=100, align="center"),
    Column("severity", "Severidade", width=95, align="center"),
    Column("value", "Valor Detectado", width=220, tooltip=True),
    Column("recommendation", "Recomendação Técnica", stretch=True, tooltip=True),
]


def _status_color_mapper(rec: Dict[str, Any], key: str) -> Optional[str]:
    """Define a cor de destaque para status e severidade na DataTableView."""
    if key == "status":
        st = rec.get("status")
        if st == "OK":
            return "#10B981"  # Verde esmeralda
        if st == "Aviso":
            return "#F59E0B"  # Âmbar
        if st == "Ausente":
            return "#EF4444"  # Vermelho
        if st == "Informativo":
            return "#60A5FA"  # Azul claro
    elif key == "severity":
        sev = rec.get("severity")
        if sev == "Alta":
            return "#EF4444"
        if sev == "Média":
            return "#F59E0B"
        if sev == "Baixa":
            return "#10B981"
        if sev == "Informativa":
            return "#9CA3AF"
    return None


@register
class HttpHeadersTool(Tool):
    id = "security.http_headers"
    name = "Auditor de Cabeçalhos HTTP"
    category = "Segurança"
    description = "Auditoria defensiva de cabeçalhos de segurança web (HSTS, CSP, X-Frame-Options, etc.) com pontuação e recomendações"
    keywords = ["cabeçalhos", "headers", "segurança", "hsts", "csp", "owasp", "http", "clickjacking", "auditoria", "defensivo"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HttpHeadersView(self, parent)


class HttpHeadersView(QWidget):
    def __init__(self, tool: HttpHeadersTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._last_result: Optional[HeaderAuditResult] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Aviso Ético e Defensivo Obrigatório
        notice_card = QFrame()
        notice_card.setObjectName("Card")
        n_lay = QVBoxLayout(notice_card)
        n_lay.setContentsMargins(14, 10, 14, 10)
        lbl_notice = QLabel(
            "<b>Auditoria Defensiva e Autodiagnóstico:</b> "
            "Esta ferramenta realiza exclusivamente uma requisição pública padrão (GET HTTP) para "
            "inspecionar os cabeçalhos de resposta do seu próprio site ou servidor. Nenhum payload, tentativa "
            "de invasão, injeção ou sobrecarga é executada."
        )
        lbl_notice.setWordWrap(True)
        lbl_notice.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        n_lay.addWidget(lbl_notice)
        root.addWidget(notice_card)

        # Barra de Entrada de URL
        input_card = QFrame()
        input_card.setObjectName("Card")
        in_lay = QHBoxLayout(input_card)
        in_lay.setContentsMargins(14, 12, 14, 12)
        in_lay.setSpacing(10)

        in_lay.addWidget(QLabel("URL do Site:"))
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("https://seusite.com.br")
        self.txt_url.returnPressed.connect(self._run_audit)
        in_lay.addWidget(self.txt_url, stretch=1)

        self.btn_audit = QPushButton("Auditar Cabeçalhos")
        self.btn_audit.setProperty("accent", True)
        self.btn_audit.clicked.connect(self._run_audit)
        in_lay.addWidget(self.btn_audit)

        root.addWidget(input_card)

        # Painel de Resultado e Resumo da Nota
        self.result_card = QFrame()
        self.result_card.setObjectName("Card")
        r_lay = QHBoxLayout(self.result_card)
        r_lay.setContentsMargins(16, 14, 16, 14)
        r_lay.setSpacing(16)

        # Badge Grande da Nota (A+, A, B, C, D, F)
        self.lbl_grade = QLabel("-")
        self.lbl_grade.setFixedSize(68, 68)
        self.lbl_grade.setAlignment(Qt.AlignCenter)
        self.lbl_grade.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.lbl_grade.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.08); "
            "border: 2px solid rgba(255, 255, 255, 0.2); "
            "border-radius: 10px; color: #ffffff;"
        )
        r_lay.addWidget(self.lbl_grade)

        # Textos de Resumo
        meta_lay = QVBoxLayout()
        meta_lay.setSpacing(4)
        self.lbl_target_info = QLabel("Informe uma URL acima e clique em 'Auditar Cabeçalhos'.")
        self.lbl_target_info.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        meta_lay.addWidget(self.lbl_target_info)

        self.lbl_summary_desc = QLabel(
            "A análise verificará HSTS, CSP, X-Frame-Options, Referrer-Policy, "
            "Permissions-Policy e potenciais vazamentos de versão de servidor."
        )
        self.lbl_summary_desc.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 11px;")
        self.lbl_summary_desc.setWordWrap(True)
        meta_lay.addWidget(self.lbl_summary_desc)

        r_lay.addLayout(meta_lay, stretch=1)

        # Botão de Exportar Relatório
        self.btn_export = QPushButton("Exportar Relatório...")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_report)
        r_lay.addWidget(self.btn_export)

        root.addWidget(self.result_card)

        # Tabela de Achados (DataTableView) + Detalhes do Cabeçalho
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # Container da Tabela
        table_container = QWidget()
        t_lay = QVBoxLayout(table_container)
        t_lay.setContentsMargins(0, 0, 0, 0)
        t_lay.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar Achados:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtrar por nome de cabeçalho, status ou recomendação...")
        self.txt_filter.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.txt_filter, stretch=1)
        t_lay.addLayout(filter_row)

        self.table = DataTableView(COLUMNS, key="header", parent=self)
        self.table.source_model.foreground = _status_color_mapper
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)
        t_lay.addWidget(self.table)
        splitter.addWidget(table_container)

        # Painel Inferior de Detalhes
        detail_card = QFrame()
        detail_card.setObjectName("Card")
        d_lay = QVBoxLayout(detail_card)
        d_lay.setContentsMargins(12, 10, 12, 10)
        d_lay.setSpacing(6)

        d_lay.addWidget(QLabel("<b>Detalhes e Impacto do Cabeçalho Selecionado:</b>"))
        self.txt_detail = QTextEdit()
        self.txt_detail.setReadOnly(True)
        self.txt_detail.setFont(QFont("Segoe UI", 9))
        self.txt_detail.setPlaceholderText("Selecione um cabeçalho na tabela para ver a descrição detalhada e o impacto de segurança.")
        self.txt_detail.setFixedHeight(85)
        d_lay.addWidget(self.txt_detail)
        splitter.addWidget(detail_card)

        splitter.setSizes([320, 100])
        root.addWidget(splitter, stretch=1)

    def _run_audit(self) -> None:
        url = self.txt_url.text().strip()
        if not url:
            show_toast(self, "Informe a URL do site a ser auditado.", duration_ms=3000)
            return

        self.btn_audit.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.lbl_grade.setText("...")
        self.lbl_grade.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.08); "
            "border: 2px solid rgba(255, 255, 255, 0.2); "
            "border-radius: 10px; color: #ffffff;"
        )
        self.lbl_target_info.setText(f"Conectando e auditando '{url}'...")
        self.lbl_summary_desc.setText("Enviando requisição GET e coletando cabeçalhos de resposta...")
        self.txt_detail.clear()

        def worker(ctx) -> HeaderAuditResult:
            return audit_http_headers(url)

        def on_done(res: HeaderAuditResult) -> None:
            self.btn_audit.setEnabled(True)
            self.btn_export.setEnabled(True)
            self._display_result(res)

        def on_error(err: Exception) -> None:
            self.btn_audit.setEnabled(True)
            self.lbl_grade.setText("!")
            self.lbl_grade.setStyleSheet(
                "background-color: rgba(239, 68, 68, 0.2); "
                "border: 2px solid #ef4444; "
                "border-radius: 10px; color: #ef4444;"
            )
            self.lbl_target_info.setText("Falha na requisição de auditoria")
            self.lbl_summary_desc.setText(f"Erro ao acessar {url}: {err}")
            show_toast(self, f"Erro na conexão: {err}", duration_ms=4000)

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _display_result(self, res: HeaderAuditResult) -> None:
        self._last_result = res

        # Badge e cor da nota
        grade = res.grade
        color_map = {
            "A+": ("#10B981", "rgba(16, 185, 129, 0.15)"),
            "A":  ("#10B981", "rgba(16, 185, 129, 0.15)"),
            "B":  ("#3B82F6", "rgba(59, 130, 246, 0.15)"),
            "C":  ("#F59E0B", "rgba(245, 158, 11, 0.15)"),
            "D":  ("#F97316", "rgba(249, 115, 22, 0.15)"),
            "F":  ("#EF4444", "rgba(239, 68, 68, 0.15)"),
        }
        fg, bg = color_map.get(grade, ("#FFFFFF", "rgba(255, 255, 255, 0.08)"))

        self.lbl_grade.setText(grade)
        self.lbl_grade.setStyleSheet(
            f"background-color: {bg}; border: 2px solid {fg}; "
            f"border-radius: 10px; color: {fg};"
        )

        proto = "HTTPS" if res.is_https else "HTTP (Não Criptografado)"
        self.lbl_target_info.setText(
            f"{res.effective_url}  •  Status {res.status_code}  •  {proto}  •  Pontuação: {res.score}/100"
        )
        self.lbl_summary_desc.setText(res.summary)

        # Popula tabela com os achados
        records = [f.to_dict() for f in res.findings]
        self.table.set_records(records)
        self.table.sortByColumn(1, Qt.AscendingOrder)
        show_toast(self, f"Auditoria concluída: Nota {grade} ({res.score}/100)!", duration_ms=3000)

    def _on_filter_changed(self, text: str) -> None:
        self.table.set_filter(text)

    def _on_row_selected(self) -> None:
        selected_indexes = self.table.selectionModel().selectedRows()
        if not selected_indexes or not self._last_result:
            return

        row = selected_indexes[0].row()
        src_row = self.table.proxy.mapToSource(selected_indexes[0]).row()
        rec = self.table.source_model._rows[src_row]

        hdr_name = rec.get("header", "")
        finding = next((f for f in self._last_result.findings if f.header == hdr_name), None)
        if finding:
            detail_text = (
                f"Cabeçalho: {finding.header}\n"
                f"Status: {finding.status} (Severidade: {finding.severity})\n"
                f"Valor Detectado: {finding.value}\n\n"
                f"Descrição de Segurança: {finding.description}\n"
                f"Recomendação de Correção: {finding.recommendation}"
            )
            self.txt_detail.setPlainText(detail_text)

    def _export_report(self) -> None:
        if not self._last_result:
            return

        res = self._last_result
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Relatório de Auditoria de Cabeçalhos",
            "auditoria_cabecalhos_seguranca.md",
            "Arquivo Markdown (*.md);;Texto Simples (*.txt)"
        )
        if not save_path:
            return

        lines = [
            "# Relatório de Auditoria de Cabeçalhos HTTP de Segurança",
            "",
            f"- **URL Auditada:** {res.target_url}",
            f"- **URL Efetiva:** {res.effective_url}",
            f"- **Status HTTP:** {res.status_code}",
            f"- **Protocolo:** {'HTTPS' if res.is_https else 'HTTP'}",
            f"- **Nota Final:** {res.grade} ({res.score}/100 pontos)",
            f"- **Resumo:** {res.summary}",
            "",
            "## Resultados Detalhados por Cabeçalho",
            "",
            "| Cabeçalho | Status | Severidade | Valor Detectado | Recomendação |",
            "| :--- | :---: | :---: | :--- | :--- |",
        ]

        for f in res.findings:
            v = f.value.replace("\n", " ").replace("|", "/")
            r = f.recommendation.replace("\n", " ").replace("|", "/")
            lines.append(f"| {f.header} | {f.status} | {f.severity} | `{v}` | {r} |")

        lines.extend([
            "",
            "---",
            "*Gerado pelo All the Utils / WinToolbox — Ferramenta Defensiva de Auditoria de Segurança.*"
        ])

        Path(save_path).write_text("\n".join(lines), encoding="utf-8")
        show_toast(self, "Relatório exportado com sucesso!", duration_ms=2500)
