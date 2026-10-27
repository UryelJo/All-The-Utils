"""
Ferramenta: Analisador de Tempo de Inicialização (Boot Performance).
Mede a velocidade de inicialização do Windows e histórico do Diagnostics-Performance.
"""
from typing import Any, Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.boot_analyzer.logic import (
    BootEventRecord,
    calculate_boot_summary,
    query_boot_performance_events,
)


@register
class BootAnalyzerTool(Tool):
    id = "system.boot_analyzer"
    name = "Analisador de Inicialização (Boot)"
    category = "Sistema"
    description = "Analise o tempo de inicialização do Windows (Event ID 100), tempo até tela de login e histórico"
    keywords = ["boot", "inicializacao", "diagnostico", "desempenho", "lentidao", "startup", "event 100", "tempo"]

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("Histórico de Desempenho de Inicialização")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("Atualizar Histórico")
        self.btn_refresh.clicked.connect(self._load_boot_history)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Cards de Resumo
        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(12)

        # Card 1: Último Boot
        card_latest = QFrame()
        card_latest.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;")
        l_layout = QVBoxLayout(card_latest)
        l_layout.addWidget(QLabel("ÚLTIMO BOOT"))
        self.lbl_latest_time = QLabel("-")
        self.lbl_latest_time.setStyleSheet("font-size: 22px; font-weight: 700; color: #0284c7;")
        l_layout.addWidget(self.lbl_latest_time)
        self.lbl_latest_status = QLabel("-")
        l_layout.addWidget(self.lbl_latest_status)
        summary_grid.addWidget(card_latest, 0, 0)

        # Card 2: Média
        card_avg = QFrame()
        card_avg.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;")
        a_layout = QVBoxLayout(card_avg)
        a_layout.addWidget(QLabel("TEMPO MÉDIO"))
        self.lbl_avg_time = QLabel("-")
        self.lbl_avg_time.setStyleSheet("font-size: 22px; font-weight: 700; color: #334155;")
        a_layout.addWidget(self.lbl_avg_time)
        self.lbl_avg_breakdown = QLabel("Login: - / Pós: -")
        a_layout.addWidget(self.lbl_avg_breakdown)
        summary_grid.addWidget(card_avg, 0, 1)

        # Card 3: Mais Rápido
        card_fastest = QFrame()
        card_fastest.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;")
        f_layout = QVBoxLayout(card_fastest)
        f_layout.addWidget(QLabel("BOOT MAIS RÁPIDO"))
        self.lbl_fastest_time = QLabel("-")
        self.lbl_fastest_time.setStyleSheet("font-size: 22px; font-weight: 700; color: #16a34a;")
        f_layout.addWidget(self.lbl_fastest_time)
        self.lbl_fastest_sub = QLabel("Melhor marca registrada")
        f_layout.addWidget(self.lbl_fastest_sub)
        summary_grid.addWidget(card_fastest, 0, 2)

        main_layout.addLayout(summary_grid)

        # Tabela de Histórico
        columns = [
            Column("timestamp", "Data e Hora", width=180),
            Column("total_boot", "Tempo Total (s)", width=130),
            Column("main_path", "Tempo até Login (s)", width=150),
            Column("post_boot", "Tempo Pós-Login (s)", width=150),
            Column("status_label", "Classificação", width=160),
        ]
        self.table = DataTableView(columns, key="timestamp", parent=container)
        main_layout.addWidget(self.table)

        self._load_boot_history()
        return container

    def _load_boot_history(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_title.setText("Consultando registros de boot no log do Windows...")

        TaskRunner.run(
            query_boot_performance_events,
            on_success=self._on_load_success,
            on_error=self._on_load_error
        )

    def _on_load_success(self, records: List[BootEventRecord]) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_title.setText("Histórico de Desempenho de Inicialização")

        if not records:
            self.lbl_latest_time.setText("N/A")
            self.lbl_latest_status.setText("Nenhum evento registrado ainda")
            return

        summary = calculate_boot_summary(records)
        latest = records[0]

        self.lbl_latest_time.setText(f"{latest.total_boot_sec:.1f} s")
        self.lbl_latest_status.setText(latest.status_label)

        self.lbl_avg_time.setText(f"{summary['avg_total_sec']:.1f} s")
        self.lbl_avg_breakdown.setText(f"Login: {summary['avg_main_sec']:.1f}s | Pós: {summary['avg_post_sec']:.1f}s")

        self.lbl_fastest_time.setText(f"{summary['fastest_sec']:.1f} s")

        rows = [
            {
                "timestamp": r.timestamp,
                "total_boot": f"{r.total_boot_sec:.1f} s",
                "main_path": f"{r.main_path_sec:.1f} s",
                "post_boot": f"{r.post_boot_sec:.1f} s",
                "status_label": r.status_label,
            }
            for r in records
        ]
        self.table.set_records(rows)

    def _on_load_error(self, err: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_title.setText(f"Erro ao consultar eventos: {err}")
