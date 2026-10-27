"""
Interface gráfica do Calculador e Explicador de Expressões Cron.
"""
from datetime import datetime
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.cron_calculator.logic import (
    PRESETS, explain_cron, get_next_cron_occurrences
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("dev.cron_calculator.ui")


@register
class CronCalculatorTool(Tool):
    id = "dev.cron_calculator"
    name = "Calculador de Cron"
    category = "Desenvolvimento"
    description = "Calculadora e explicador de expressões Cron: descreve em português claro a frequência de execução agendada e calcula as próximas datas de disparo."
    keywords = ["cron", "schedule", "agendamento", "timer", "tarefa", "crontab", "dev", "tempo", "horario"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CronCalculatorView(self, parent)


class CronCalculatorView(QWidget):
    def __init__(self, tool: CronCalculatorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()
        self._calculate()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Calculador de Expressões Cron",
            "Análise de sintaxe, tradução explicativa em português e projeção detalhada das próximas execuções agendadas."
        ))

        # 1. Painel de Expressão e Presets
        input_box = QGroupBox("Expressão Cron")
        input_layout = QVBoxLayout(input_box)
        input_layout.setSpacing(8)

        # Linha de presets
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Exemplos Frequentes:"))
        self.combo_presets = QComboBox()
        self.combo_presets.addItem("Selecione um modelo pronto...", "")
        for label, expr in PRESETS:
            self.combo_presets.addItem(f"{label} ({expr})", expr)
        self.combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self.combo_presets, stretch=1)
        input_layout.addLayout(preset_row)

        # Linha de entrada da expressão
        expr_row = QHBoxLayout()
        expr_row.addWidget(QLabel("Expressão:"))
        self.edit_expr = QLineEdit("*/15 * * * *")
        self.edit_expr.setFont(QFont("Cascadia Mono", 11))
        self.edit_expr.textChanged.connect(self._calculate)
        expr_row.addWidget(self.edit_expr, stretch=1)

        btn_copy_expr = QPushButton("Copiar Expressão")
        btn_copy_expr.clicked.connect(self._copy_expression)
        expr_row.addWidget(btn_copy_expr)
        input_layout.addLayout(expr_row)

        # Dica de campos
        lbl_hint = QLabel("Formato: <minuto> <hora> <dia-do-mês> <mês> <dia-da-semana> (0 ou 7 = Domingo)")
        lbl_hint.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        input_layout.addWidget(lbl_hint)

        root.addWidget(input_box)

        # 2. Painel de Explicação Semântica
        desc_box = QGroupBox("Significado em Português")
        desc_layout = QVBoxLayout(desc_box)
        self.lbl_explanation = QLabel("Calculando...")
        self.lbl_explanation.setWordWrap(True)
        self.lbl_explanation.setStyleSheet("font-size: 13px; font-weight: bold; color: #60A5FA; padding: 4px 0;")
        desc_layout.addWidget(self.lbl_explanation)
        root.addWidget(desc_box)

        # 3. Painel de Próximas Execuções
        results_box = QGroupBox("Próximas Execuções Agendadas")
        results_layout = QVBoxLayout(results_box)
        results_layout.setSpacing(8)

        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Quantidade de execuções a simular:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 100)
        self.spin_count.setValue(10)
        self.spin_count.valueChanged.connect(self._calculate)
        controls_row.addWidget(self.spin_count)
        controls_row.addStretch(1)

        btn_copy_list = QPushButton("Copiar Todas as Datas")
        btn_copy_list.clicked.connect(self._copy_occurrences)
        controls_row.addWidget(btn_copy_list)
        results_layout.addLayout(controls_row)

        self.list_occurrences = QListWidget()
        self.list_occurrences.setFont(QFont("Cascadia Mono", 10))
        results_layout.addWidget(self.list_occurrences, stretch=1)

        root.addWidget(results_box, stretch=1)

    def _on_preset_selected(self, index: int) -> None:
        expr = self.combo_presets.currentData()
        if expr:
            self.edit_expr.setText(str(expr))

    def _calculate(self) -> None:
        expr = self.edit_expr.text().strip()
        if not expr:
            self.lbl_explanation.setText("Digite uma expressão cron válida.")
            self.list_occurrences.clear()
            return

        # Explicação semântica
        explanation = explain_cron(expr)
        self.lbl_explanation.setText(explanation)

        # Próximas execuções
        self.list_occurrences.clear()
        try:
            count = self.spin_count.value()
            now = datetime.now()
            dates = get_next_cron_occurrences(expr, count=count, start_time=now)

            dow_pt = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

            for i, dt in enumerate(dates, 1):
                weekday_name = dow_pt[dt.weekday()]
                item_str = f"#{i:02d}  —  {dt.strftime('%d/%m/%Y %H:%M:%S')} ({weekday_name})"
                item = QListWidgetItem(item_str)
                self.list_occurrences.addItem(item)

        except Exception as exc:
            self.list_occurrences.addItem(f"Erro no cálculo: {exc}")

    def _copy_expression(self) -> None:
        expr = self.edit_expr.text().strip()
        if expr:
            QApplication.clipboard().setText(expr)
            show_toast(self, "Expressão copiada para a área de transferência!")

    def _copy_occurrences(self) -> None:
        lines = []
        for i in range(self.list_occurrences.count()):
            lines.append(self.list_occurrences.item(i).text())
        if lines:
            QApplication.clipboard().setText("\n".join(lines))
            show_toast(self, f"{len(lines)} execuções copiadas!", duration_ms=1800)
