"""
Interface gráfica do Registrador de Tempo (Time Tracker).
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.time_tracker.logic import (
    add_manual_time_entry, delete_time_entry, export_time_entries_csv,
    format_duration, get_active_time_entry, get_project_time_summary,
    list_time_entries, start_time_entry, stop_time_entry
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("productivity.time_tracker.ui")


@register
class TimeTrackerTool(Tool):
    id = "productivity.time_tracker"
    name = "Registrador de Tempo"
    category = "Produtividade"
    description = "Controle de tempo e horas trabalhadas por projeto e atividade com cronômetro e exportação"
    keywords = ["tempo", "time tracker", "horas", "cronometro", "trabalho", "projeto", "produtividade"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TimeTrackerView(self, parent)


class TimeTrackerView(QWidget):
    def __init__(self, tool: TimeTrackerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._active_entry_id: Optional[int] = None
        self._active_start_time: Optional[datetime] = None

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._check_initial_active_state()
        self._refresh_history()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Registrador de Tempo (Time Tracker)",
            "Acompanhe com precisão onde seu tempo é investido por tarefa e categoria, com relatórios exportáveis."
        ))

        # 1. Painel do Cronômetro Ativo
        active_card = QFrame()
        active_card.setProperty("class", "card")
        active_card.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 12px; }")

        card_layout = QHBoxLayout(active_card)
        card_layout.setSpacing(12)

        # Entrada de Atividade
        inputs_layout = QVBoxLayout()
        inputs_layout.setSpacing(6)

        self.edit_activity = QLineEdit()
        self.edit_activity.setPlaceholderText("No que você está trabalhando agora?")
        self.edit_activity.setFont(QFont("Segoe UI", 10))
        inputs_layout.addWidget(self.edit_activity)

        proj_row = QHBoxLayout()
        proj_row.addWidget(QLabel("Projeto:"))
        self.combo_project = QComboBox()
        self.combo_project.setEditable(True)
        self.combo_project.addItems(["Geral", "Desenvolvimento", "Design", "Reuniões", "Estudos", "Suporte"])
        proj_row.addWidget(self.combo_project, stretch=1)
        inputs_layout.addLayout(proj_row)

        card_layout.addLayout(inputs_layout, stretch=2)

        # Display do Cronômetro
        self.lbl_clock = QLabel("00:00:00")
        self.lbl_clock.setFont(QFont("Cascadia Mono", 24, QFont.Weight.Bold))
        self.lbl_clock.setStyleSheet("color: #60A5FA; padding: 0 16px;")
        card_layout.addWidget(self.lbl_clock)

        # Botão Iniciar / Parar
        self.btn_toggle = QPushButton("Iniciar Atividade")
        self.btn_toggle.setProperty("class", "primary")
        self.btn_toggle.setFixedSize(140, 42)
        self.btn_toggle.clicked.connect(self._toggle_timer)
        card_layout.addWidget(self.btn_toggle)

        root.addWidget(active_card)

        # 2. Resumo por Projetos
        self.lbl_summary = QLabel("Carregando resumo...")
        self.lbl_summary.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        root.addWidget(self.lbl_summary)

        # 3. Histórico e Tabela
        hist_box = QGroupBox("Histórico de Registros")
        hist_layout = QVBoxLayout(hist_box)
        hist_layout.setSpacing(8)

        # Barra de Ações do Histórico
        top_hist = QHBoxLayout()
        top_hist.addWidget(QLabel("Filtrar Projeto:"))
        self.combo_filter_proj = QComboBox()
        self.combo_filter_proj.addItem("Todos os Projetos", "")
        self.combo_filter_proj.currentIndexChanged.connect(self._refresh_history)
        top_hist.addWidget(self.combo_filter_proj)
        top_hist.addStretch(1)

        btn_manual = QPushButton("Adicionar Manualmente...")
        btn_manual.clicked.connect(self._open_manual_entry_dialog)
        top_hist.addWidget(btn_manual)

        btn_export = QPushButton("Exportar CSV")
        btn_export.clicked.connect(self._export_csv)
        top_hist.addWidget(btn_export)

        hist_layout.addLayout(top_hist)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Atividade", "Projeto", "Início", "Duração", "Ação"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 75)
        hist_layout.addWidget(self.table)

        root.addWidget(hist_box, stretch=1)

    def _check_initial_active_state(self) -> None:
        active = get_active_time_entry()
        if active:
            self._active_entry_id = active["id"]
            self._active_start_time = datetime.fromisoformat(active["start_time"])
            self.edit_activity.setText(active["activity"])
            self.combo_project.setCurrentText(active["project"])
            self.btn_toggle.setText("Parar e Salvar")
            self.btn_toggle.setStyleSheet("background-color: #EF4444; color: white;")
            self._tick_timer.start()

    def _toggle_timer(self) -> None:
        if self._active_entry_id:
            # Parar
            stop_time_entry(self._active_entry_id)
            self._active_entry_id = None
            self._active_start_time = None
            self._tick_timer.stop()

            self.btn_toggle.setText("Iniciar Atividade")
            self.btn_toggle.setStyleSheet("")
            self.lbl_clock.setText("00:00:00")
            self.lbl_clock.setStyleSheet("color: #60A5FA; padding: 0 16px;")
            show_toast(self, "Atividade concluída e registrada!")
            self._refresh_history()
        else:
            # Iniciar
            act = self.edit_activity.text().strip() or "Trabalho sem título"
            proj = self.combo_project.currentText().strip() or "Geral"

            entry_id = start_time_entry(activity=act, project=proj)
            self._active_entry_id = entry_id
            self._active_start_time = datetime.now()
            self._tick_timer.start()

            self.btn_toggle.setText("Parar e Salvar")
            self.btn_toggle.setStyleSheet("background-color: #EF4444; color: white;")
            self.lbl_clock.setStyleSheet("color: #10B981; padding: 0 16px;")
            show_toast(self, f"Cronômetro iniciado para '{act}'!")

    def _on_tick(self) -> None:
        if not self._active_start_time:
            return
        elapsed = int((datetime.now() - self._active_start_time).total_seconds())
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        self.lbl_clock.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

    def _refresh_history(self) -> None:
        proj_filter = self.combo_filter_proj.currentData() or ""
        entries = list_time_entries(project=proj_filter)

        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            # Atividade
            self.table.setItem(row, 0, QTableWidgetItem(e["activity"]))
            # Projeto
            self.table.setItem(row, 1, QTableWidgetItem(e["project"]))
            # Início
            try:
                st = datetime.fromisoformat(e["start_time"]).strftime("%d/%m %H:%M")
            except Exception:
                st = e["start_time"]
            self.table.setItem(row, 2, QTableWidgetItem(st))
            # Duração
            dur_str = format_duration(e["duration_seconds"])
            self.table.setItem(row, 3, QTableWidgetItem(dur_str))

            # Botão excluir
            btn_del = QPushButton("Excluir")
            btn_del.setStyleSheet("font-size: 10px; padding: 2px;")
            btn_del.clicked.connect(lambda checked=False, eid=e["id"]: self._delete_entry(eid))
            self.table.setCellWidget(row, 4, btn_del)

        # Atualiza Resumo de Projetos
        summary = get_project_time_summary()
        summary_parts = [f"{proj}: {format_duration(sec)}" for proj, sec in summary.items()]
        if summary_parts:
            self.lbl_summary.setText("Tempo Acumulado por Projeto: " + "  •  ".join(summary_parts))
        else:
            self.lbl_summary.setText("Nenhuma atividade registrada ainda.")

        # Atualiza combo de filtro se necessário
        current_data = self.combo_filter_proj.currentData()
        self.combo_filter_proj.blockSignals(True)
        self.combo_filter_proj.clear()
        self.combo_filter_proj.addItem("Todos os Projetos", "")
        for p in summary.keys():
            self.combo_filter_proj.addItem(p, p)
        idx = self.combo_filter_proj.findData(current_data)
        if idx >= 0:
            self.combo_filter_proj.setCurrentIndex(idx)
        self.combo_filter_proj.blockSignals(False)

    def _delete_entry(self, entry_id: int) -> None:
        delete_time_entry(entry_id)
        self._refresh_history()

    def _export_csv(self) -> None:
        proj_filter = self.combo_filter_proj.currentData() or ""
        entries = list_time_entries(project=proj_filter, limit=5000)
        if not entries:
            show_toast(self, "Nenhum registro para exportar.")
            return

        csv_content = export_time_entries_csv(entries)
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Registro de Tempo", "relatorio_horas.csv", "Planilha CSV (*.csv)")
        if path:
            Path(path).write_text(csv_content, encoding="utf-8-sig")
            show_toast(self, f"Arquivo exportado com sucesso em {Path(path).name}!")

    def _open_manual_entry_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Adicionar Registro Manual")
        dlg.setFixedWidth(380)

        layout = QVBoxLayout(dlg)
        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Atividade:"), 0, 0)
        edit_act = QLineEdit()
        grid.addWidget(edit_act, 0, 1)

        grid.addWidget(QLabel("Projeto:"), 1, 0)
        edit_proj = QLineEdit("Geral")
        grid.addWidget(edit_proj, 1, 1)

        grid.addWidget(QLabel("Duração (Minutos):"), 2, 0)
        spin_mins = QSpinBox()
        spin_mins.setRange(1, 1440)
        spin_mins.setValue(30)
        grid.addWidget(spin_mins, 2, 1)

        layout.addLayout(grid)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dlg.reject)
        btn_save = QPushButton("Salvar Registro")
        btn_save.setProperty("class", "primary")

        def save_and_close():
            add_manual_time_entry(
                activity=edit_act.text().strip() or "Atividade Manual",
                project=edit_proj.text().strip() or "Geral",
                duration_minutes=spin_mins.value()
            )
            dlg.accept()
            self._refresh_history()
            show_toast(self, "Registro manual adicionado!")

        btn_save.clicked.connect(save_and_close)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

        dlg.exec()
