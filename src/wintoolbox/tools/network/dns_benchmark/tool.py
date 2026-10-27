"""
Ferramenta: Benchmark e Comparador de Servidores DNS.
Testa tempo de resposta dos principais servidores (Cloudflare, Google, Quad9, OpenDNS).
"""
from typing import Any, Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.network.dns_benchmark.logic import (
    DnsBenchmarkResult,
    run_full_dns_benchmark,
)


@register
class DnsBenchmarkTool(Tool):
    id = "network.dns_benchmark"
    name = "Benchmark de Servidores DNS"
    category = "Rede e Internet"
    description = "Compare a latência e tempo de resposta de servidores DNS públicos (Cloudflare, Google, Quad9, OpenDNS)"
    keywords = ["dns", "benchmark", "latencia", "ping", "cloudflare", "google dns", "quad9", "provedor", "velocidade"]

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("Comparador de Desempenho de Servidores DNS")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()

        self.btn_run = QPushButton("Iniciar Benchmark DNS")
        self.btn_run.setStyleSheet("font-weight: 600;")
        self.btn_run.clicked.connect(self._start_benchmark)
        top_bar.addWidget(self.btn_run)
        main_layout.addLayout(top_bar)

        # Tabela DataTableView
        columns = [
            Column("rank_display", "Ranking", width=100),
            Column("name", "Provedor DNS", width=220),
            Column("ip", "Endereço IP", width=160),
            Column("avg_display", "Latência Média", width=140),
            Column("min_display", "Menor Latência", width=140),
            Column("success_display", "Taxa de Sucesso", stretch=True),
        ]
        self.table = DataTableView(columns, key="ip", parent=container)
        main_layout.addWidget(self.table)

        # Status
        self.lbl_status = QLabel("Clique em 'Iniciar Benchmark DNS' para testar a velocidade dos servidores.")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_status)

        return container

    def _start_benchmark(self) -> None:
        self.btn_run.setEnabled(False)
        self.lbl_status.setText("Medindo latência de consulta DNS na porta 53... Aguarde alguns instantes.")

        TaskRunner.run(
            run_full_dns_benchmark,
            on_success=self._on_benchmark_success,
            on_error=self._on_benchmark_error
        )

    def _on_benchmark_success(self, results: List[DnsBenchmarkResult]) -> None:
        self.btn_run.setEnabled(True)
        if not results:
            self.lbl_status.setText("Nenhum resultado obtido.")
            return

        winner = results[0]
        self.lbl_status.setText(f"Benchmark concluído! O servidor mais rápido foi {winner.name} ({winner.avg_latency_ms} ms).")
        self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")

        rows = [
            {
                "rank_display": f"#{r.rank}",
                "name": r.name,
                "ip": r.ip,
                "avg_display": f"{r.avg_latency_ms:.1f} ms" if r.avg_latency_ms < 9000 else "Timeout",
                "min_display": f"{r.min_latency_ms:.1f} ms" if r.min_latency_ms < 9000 else "-",
                "success_display": f"{r.success_rate_percent:.0f}%",
            }
            for r in results
        ]
        self.table.set_records(rows)

    def _on_benchmark_error(self, err: Exception) -> None:
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"Erro ao executar benchmark DNS: {err}")
        self.lbl_status.setStyleSheet("color: #dc2626; font-size: 12px;")
