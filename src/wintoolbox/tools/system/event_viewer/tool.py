"""
Ferramenta: Visualizador Filtrado de Logs de Eventos (Event Viewer).
Permite diagnosticar falhas de sistema e avisos recentes em System e Application com exportação CSV.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton,
    QSplitter, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.event_viewer.logic import (
    EventLogRecord,
    export_events_to_csv,
    query_windows_event_log,
)


@register
class EventViewerTool(Tool):
    id = "system.event_viewer"
    name = "Visualizador de Eventos"
    category = "Sistema"
    description = "Consulte e filtre falhas, erros e avisos recentes do Windows (System e Application) com exportação CSV"
    keywords = ["eventos", "logs", "event viewer", "erros", "avisos", "system", "application", "falhas", "crash"]

    def __init__(self) -> None:
        super().__init__()
        self._all_events: List[EventLogRecord] = []

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Filtros de Consulta Superior
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        filter_bar.addWidget(QLabel("Canal:"))
        self.cmb_log = QComboBox()
        self.cmb_log.addItems(["System", "Application", "Security"])
        filter_bar.addWidget(self.cmb_log)

        filter_bar.addWidget(QLabel("Severidade:"))
        self.cmb_severity = QComboBox()
        self.cmb_severity.addItems(["Erros e Avisos", "Apenas Erros", "Todos os Níveis"])
        filter_bar.addWidget(self.cmb_severity)

        filter_bar.addWidget(QLabel("Período:"))
        self.cmb_period = QComboBox()
        self.cmb_period.addItems(["Últimas 24 Horas", "Últimos 3 Dias", "Últimos 7 Dias"])
        filter_bar.addWidget(self.cmb_period)

        self.btn_query = QPushButton("Consultar Logs")
        self.btn_query.clicked.connect(self._run_query)
        filter_bar.addWidget(self.btn_query)

        self.btn_export = QPushButton("Exportar CSV...")
        self.btn_export.clicked.connect(self._export_csv)
        filter_bar.addWidget(self.btn_export)

        filter_bar.addStretch()
        main_layout.addLayout(filter_bar)

        # Barra de Busca Instantânea
        search_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filtrar eventos exibidos por texto, ID ou provedor...")
        self.txt_search.textChanged.connect(self._apply_search_filter)
        search_bar.addWidget(self.txt_search)
        main_layout.addLayout(search_bar)

        # Splitter Vertical: Tabela e Detalhes
        splitter = QSplitter(Qt.Vertical)

        # Tabela
        columns = [
            Column("time_created", "Data e Hora", width=160),
            Column("level_display", "Nível", width=110),
            Column("event_id", "ID", width=80),
            Column("provider_name", "Fonte / Provedor", width=180),
            Column("message_preview", "Mensagem", stretch=True),
        ]
        self.table = DataTableView(columns, key="time_created", parent=container)
        self.table.clicked.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        # Detalhe do Evento Selecionado
        detail_frame = QFrame()
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.addWidget(QLabel("<b>Detalhes da Mensagem do Evento Selecionado:</b>"))

        self.txt_details = QTextEdit()
        self.txt_details.setReadOnly(True)
        self.txt_details.setPlaceholderText("Selecione um evento na tabela para ver a descrição detalhada.")
        detail_layout.addWidget(self.txt_details)
        splitter.addWidget(detail_frame)

        splitter.setSizes([380, 160])
        main_layout.addWidget(splitter)

        # Status
        self.lbl_status = QLabel("Selecione o canal e clique em 'Consultar Logs'.")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_status)

        self._run_query()
        return container

    def _run_query(self) -> None:
        self.btn_query.setEnabled(False)
        self.lbl_status.setText("Consultando eventos do Windows via PowerShell...")

        log_name = self.cmb_log.currentText()
        sev_text = self.cmb_severity.currentText()
        if sev_text == "Apenas Erros":
            sev = "ErrorsOnly"
        elif sev_text == "Erros e Avisos":
            sev = "ErrorsAndWarnings"
        else:
            sev = "All"

        period_text = self.cmb_period.currentText()
        hours = 24
        if "3 Dias" in period_text:
            hours = 72
        elif "7 Dias" in period_text:
            hours = 168

        def _worker() -> List[EventLogRecord]:
            return query_windows_event_log(
                log_name=log_name,
                severity=sev,
                hours_back=hours,
                max_events=200
            )

        TaskRunner.run(
            _worker,
            on_success=self._on_query_success,
            on_error=self._on_query_error
        )

    def _on_query_success(self, events: List[EventLogRecord]) -> None:
        self._all_events = events
        self.btn_query.setEnabled(True)
        self.lbl_status.setText(f"{len(events)} eventos encontrados no canal '{self.cmb_log.currentText()}'.")
        self._apply_search_filter()

    def _on_query_error(self, err: Exception) -> None:
        self.btn_query.setEnabled(True)
        self.lbl_status.setText(f"Erro ao consultar eventos: {err}")

    def _apply_search_filter(self) -> None:
        q = self.txt_search.text().strip().lower()
        records: List[Dict[str, Any]] = []

        for e in self._all_events:
            if q:
                match_prov = q in e.provider_name.lower()
                match_msg = q in e.message.lower()
                match_id = q in str(e.event_id)
                if not (match_prov or match_msg or match_id):
                    continue

            records.append({
                "time_created": e.time_created,
                "level_display": e.level_display,
                "event_id": str(e.event_id),
                "provider_name": e.provider_name,
                "message_preview": e.message[:120] + "..." if len(e.message) > 120 else e.message,
                "full_message": e.message,
            })

        self.table.set_records(records)

    def _on_row_selected(self) -> None:
        rec = self.table.current_record()
        if rec:
            full_msg = rec.get("full_message") or rec.get("message_preview") or ""
            info = f"Data: {rec.get('time_created')} | Nível: {rec.get('level_display')} | ID: {rec.get('event_id')}\n"
            info += f"Provedor: {rec.get('provider_name')}\n"
            info += f"{'='*60}\n\n"
            info += full_msg
            self.txt_details.setText(info)

    def _export_csv(self) -> None:
        if not self._all_events:
            QMessageBox.information(None, "Sem dados", "Consulte os eventos antes de exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Exportar Logs de Eventos",
            "eventos_windows.csv",
            "Arquivo CSV (*.csv)"
        )
        if file_path:
            try:
                export_events_to_csv(self._all_events, Path(file_path))
                self.lbl_status.setText(f"Arquivo CSV exportado com sucesso: {Path(file_path).name}")
            except Exception as e:
                self.lbl_status.setText(f"Erro ao exportar CSV: {e}")
