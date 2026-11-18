"""
Ferramenta: Analisador de Tempo de Inicialização (Boot Performance).
Mede a velocidade de inicialização do Windows e histórico do Diagnostics-Performance.
"""
from typing import List
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import bind_admin_prompt_on_show
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.boot_analyzer.logic import (
    BootEventRecord,
    calculate_boot_summary,
    query_boot_performance_events,
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class BootAnalyzerTool(Tool):
    id = "system.boot_analyzer"
    name = "Analisador de Inicialização"
    category = "Sistema"
    description = "Analise o tempo de inicialização do Windows (Event ID 100), tempo até tela de login e histórico"
    keywords = ["boot", "inicializacao", "diagnostico", "desempenho", "lentidao", "startup", "event 100", "tempo"]

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(12)
        main_layout.addWidget(make_tool_header(self))

        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("Histórico de Desempenho de Inicialização")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("Atualizar Histórico")
        self.btn_refresh.clicked.connect(self._load_boot_history)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Cards de Resumo (utilizando o tema nativo do app, sem fundo branco hardcoded)
        t = get_current_tokens()
        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(12)

        # Card 1: Último Boot
        card_latest = QFrame()
        card_latest.setObjectName("Card")
        card_latest.setProperty("class", "card")
        l_layout = QVBoxLayout(card_latest)
        l_layout.setContentsMargins(16, 12, 16, 12)
        lbl_c1 = QLabel("ÚLTIMO BOOT")
        lbl_c1.setProperty("class", "secondary")
        l_layout.addWidget(lbl_c1)
        self.lbl_latest_time = QLabel("-")
        self.lbl_latest_time.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.accent};")
        l_layout.addWidget(self.lbl_latest_time)
        self.lbl_latest_status = QLabel("-")
        self.lbl_latest_status.setProperty("class", "secondary")
        l_layout.addWidget(self.lbl_latest_status)
        summary_grid.addWidget(card_latest, 0, 0)

        # Card 2: Média
        card_avg = QFrame()
        card_avg.setObjectName("Card")
        card_avg.setProperty("class", "card")
        a_layout = QVBoxLayout(card_avg)
        a_layout.setContentsMargins(16, 12, 16, 12)
        lbl_c2 = QLabel("TEMPO MÉDIO")
        lbl_c2.setProperty("class", "secondary")
        a_layout.addWidget(lbl_c2)
        self.lbl_avg_time = QLabel("-")
        self.lbl_avg_time.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.text_primary};")
        a_layout.addWidget(self.lbl_avg_time)
        self.lbl_avg_breakdown = QLabel("Login: - / Pós: -")
        self.lbl_avg_breakdown.setProperty("class", "secondary")
        a_layout.addWidget(self.lbl_avg_breakdown)
        summary_grid.addWidget(card_avg, 0, 1)

        # Card 3: Mais Rápido
        card_fastest = QFrame()
        card_fastest.setObjectName("Card")
        card_fastest.setProperty("class", "card")
        f_layout = QVBoxLayout(card_fastest)
        f_layout.setContentsMargins(16, 12, 16, 12)
        lbl_c3 = QLabel("BOOT MAIS RÁPIDO")
        lbl_c3.setProperty("class", "secondary")
        f_layout.addWidget(lbl_c3)
        self.lbl_fastest_time = QLabel("-")
        self.lbl_fastest_time.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.status_success};")
        f_layout.addWidget(self.lbl_fastest_time)
        self.lbl_fastest_sub = QLabel("Melhor marca registrada")
        self.lbl_fastest_sub.setProperty("class", "secondary")
        f_layout.addWidget(self.lbl_fastest_sub)
        summary_grid.addWidget(card_fastest, 0, 2)

        main_layout.addLayout(summary_grid)

        # Tabela de Histórico
        columns = [
            Column("timestamp", "Data e Hora", width=210),
            Column("total_boot", "Tempo Total (s)", width=130),
            Column("main_path", "Tempo até Login (s)", width=150),
            Column("post_boot", "Tempo Pós-Login (s)", width=150),
            Column("status_label", "Classificação", stretch=True),
        ]
        self.table = DataTableView(columns, key="timestamp", parent=container)
        main_layout.addWidget(self.table, stretch=1)

        bind_admin_prompt_on_show(
            container,
            tool_name=self.name,
            reason="O canal 'Diagnostics-Performance/Operational' do Windows exige Administrador para detalhamento completo do Event ID 100.",
        )

        self._load_boot_history()
        return container

    def _load_boot_history(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_title.setText("Consultando registros de boot no log do Windows...")

        TaskRunner.run(
            query_boot_performance_events,
            on_success=self._on_load_success,
            on_error=self._on_load_error,
        )

    def _on_load_success(self, records: List[BootEventRecord]) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_title.setText(f"Histórico de Desempenho de Inicialização ({len(records)} registro(s))")

        if not records:
            self.lbl_latest_time.setText("Sem dados")
            self.lbl_latest_status.setText("Execute como Administrador para ler o canal operacional")
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
