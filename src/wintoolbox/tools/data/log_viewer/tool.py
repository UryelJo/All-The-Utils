"""
Interface gráfica Fluent para o Visualizador de Arquivos de Log.
Suporte a filtragem instantânea por severidade, busca por regex, monitoramento contínuo (tail) e atalho para o log do app.
"""
import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.log_viewer.logic import (
    filter_log_records,
    get_file_info,
    parse_log_line,
    read_tail_lines,
)


@register
class LogViewerTool(Tool):
    id = "data.log_viewer"
    name = "Visualizador de Logs"
    description = "Leitor de arquivos de log com filtro por severidade (INFO, WARN, ERROR), busca por regex e modo tail."
    category = "Dados e Estruturas"
    icon = "DocumentText"
    tags = ["log", "viewer", "tail", "monitor", "debug", "error", "warn", "info"]

    def __init__(self) -> None:
        super().__init__()
        self._current_file: Optional[str] = None
        self._raw_records: List[dict] = []
        self._tail_timer = QTimer()
        self._tail_timer.setInterval(2000)

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior de Ações
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_open = QPushButton("Abrir Arquivo...")
        btn_open_app_log = QPushButton("Abrir Log do WinToolbox")
        btn_reload = QPushButton("Recarregar")

        self.chk_tail = QCheckBox("Seguir Final (Tail Automático)")

        top_bar.addWidget(btn_open)
        top_bar.addWidget(btn_open_app_log)
        top_bar.addWidget(btn_reload)
        top_bar.addWidget(self.chk_tail)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        # Barra de Filtros
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        filter_bar.addWidget(QLabel("Severidade:"))
        self.combo_level = QComboBox()
        self.combo_level.addItems(["ALL", "FATAL", "ERROR", "WARN", "INFO", "DEBUG", "TRACE"])
        filter_bar.addWidget(self.combo_level)

        filter_bar.addWidget(QLabel("Buscar:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Filtrar por texto ou regex...")
        filter_bar.addWidget(self.edit_search, 1)

        self.chk_regex = QCheckBox("Regex")
        filter_bar.addWidget(self.chk_regex)

        btn_clear_filter = QPushButton("Limpar Filtro")
        filter_bar.addWidget(btn_clear_filter)

        layout.addLayout(filter_bar)

        self.lbl_status = QLabel("Nenhum arquivo carregado.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Tabela de Visualização de Logs
        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(3)
        self.table_logs.setHorizontalHeaderLabels(["Nível", "Horário", "Mensagem do Log"])
        self.table_logs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_logs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_logs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_logs.setAlternatingRowColors(True)

        layout.addWidget(self.table_logs, 1)

        # Conexões
        btn_open.clicked.connect(self._on_open_file)
        btn_open_app_log.clicked.connect(self._on_open_app_log)
        btn_reload.clicked.connect(self._on_reload)
        btn_clear_filter.clicked.connect(self._on_clear_filter)
        self.chk_tail.toggled.connect(self._on_tail_toggled)
        self.combo_level.currentTextChanged.connect(self._apply_filters)
        self.edit_search.textChanged.connect(self._apply_filters)
        self.chk_regex.toggled.connect(self._apply_filters)
        self._tail_timer.timeout.connect(self._on_tail_tick)

        return container

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Abrir Arquivo de Log",
            "",
            "Arquivos de Log (*.log *.txt);;Todos os Arquivos (*.*)",
        )
        if path:
            self._load_file(path)

    def _on_open_app_log(self) -> None:
        appdata = os.getenv("APPDATA", "")
        app_log_path = Path(appdata) / "AllTheUtils" / "logs" / "app.log"
        if not app_log_path.exists():
            # Tenta pasta local de desenvolvimento
            local_log = Path("logs/app.log")
            if local_log.exists():
                app_log_path = local_log
            else:
                QMessageBox.information(None, "Arquivo não encontrado", f"O log da aplicação ainda não foi criado em:\n{app_log_path}")
                return
        self._load_file(str(app_log_path))

    def _load_file(self, path: str) -> None:
        self._current_file = path
        lines = read_tail_lines(path, max_lines=1000)
        self._raw_records = [parse_log_line(l) for l in lines]
        self._apply_filters()

    def _on_reload(self) -> None:
        if self._current_file:
            self._load_file(self._current_file)

    def _on_tail_toggled(self, checked: bool) -> None:
        if checked:
            self._tail_timer.start()
        else:
            self._tail_timer.stop()

    def _on_tail_tick(self) -> None:
        if self._current_file and Path(self._current_file).exists():
            lines = read_tail_lines(self._current_file, max_lines=1000)
            self._raw_records = [parse_log_line(l) for l in lines]
            self._apply_filters()
            self.table_logs.scrollToBottom()

    def _on_clear_filter(self) -> None:
        self.combo_level.setCurrentText("ALL")
        self.edit_search.clear()
        self.chk_regex.setChecked(False)

    def _apply_filters(self) -> None:
        if not self._current_file:
            return

        level = self.combo_level.currentText()
        query = self.edit_search.text()
        is_regex = self.chk_regex.isChecked()

        filtered = filter_log_records(self._raw_records, level_filter=level, text_query=query, is_regex=is_regex)

        self.table_logs.clearContents()
        self.table_logs.setRowCount(len(filtered))

        color_map = {
            "FATAL": QColor("#b71c1c"),
            "ERROR": QColor("#d32f2f"),
            "WARN": QColor("#ef6c00"),
            "INFO": QColor("#1976d2"),
            "DEBUG": QColor("#757575"),
            "TRACE": QColor("#9e9e9e"),
        }

        for idx, rec in enumerate(filtered):
            lvl = rec["level"]
            item_lvl = QTableWidgetItem(lvl)
            item_ts = QTableWidgetItem(rec["timestamp"])
            item_msg = QTableWidgetItem(rec["message"])

            if lvl in color_map:
                item_lvl.setForeground(color_map[lvl])

            self.table_logs.setItem(idx, 0, item_lvl)
            self.table_logs.setItem(idx, 1, item_ts)
            self.table_logs.setItem(idx, 2, item_msg)

        f_info = get_file_info(self._current_file)
        self.lbl_status.setText(
            f"Arquivo: {Path(self._current_file).name} ({f_info['size_formatted']}) — "
            f"Exibindo {len(filtered)} de {len(self._raw_records)} linha(s) carregadas."
        )
