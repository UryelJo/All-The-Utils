"""
Interface gráfica do Analisador de Travamentos e Telas Azuis (BSODs).
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.crash_analyzer.logic import (
    BUGCHECK_DESCRIPTIONS, explain_bugcheck_code, list_minidump_files,
    query_system_crash_events
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.crash_analyzer.ui")


@register
class CrashAnalyzerTool(Tool):
    id = "system.crash_analyzer"
    name = "Analisador de Travamentos e BSODs"
    category = "Sistema"
    description = "Investigação de desligamentos inesperados (evento 41), telas azuis, erros WHEA e arquivos Minidump"
    keywords = ["bsod", "tela azul", "travamento", "crash", "minidump", "kernel power", "41", "whea", "dump"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CrashAnalyzerView(self, parent)


class CrashAnalyzerView(QWidget):
    def __init__(self, tool: CrashAnalyzerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        top_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Atualizar Análise")
        self.btn_refresh.setProperty("accent", True)
        self.btn_refresh.clicked.connect(self._refresh_all_async)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_status = QLabel("Pronto para escanear logs de travamento.")
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        self._setup_events_tab()
        self._setup_minidumps_tab()
        self._setup_dictionary_tab()
        layout.addWidget(self.tabs, stretch=1)

        # Carrega dados
        self._refresh_all_async()

    def _setup_events_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        self.table_events = QTableWidget(0, 4)
        self.table_events.setHorizontalHeaderLabels(["Data e Hora", "ID", "Tipo do Travamento", "Resumo"])
        self.table_events.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_events.itemSelectionChanged.connect(self._on_event_selected)
        lay.addWidget(self.table_events, stretch=2)

        lay.addWidget(QLabel("Mensagem Detalhada do Log do Windows:"))
        self.txt_detail = QTextEdit()
        self.txt_detail.setReadOnly(True)
        self.txt_detail.setMaximumHeight(130)
        lay.addWidget(self.txt_detail, stretch=1)

        self.tabs.addTab(tab, "Eventos de Falha (Kernel-Power e BSOD)")

    def _setup_minidumps_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        bar = QHBoxLayout()
        btn_open_folder = QPushButton("Abrir Pasta C:\\Windows\\Minidump")
        btn_open_folder.clicked.connect(self._open_minidump_folder)
        bar.addWidget(btn_open_folder)
        bar.addStretch()
        lay.addLayout(bar)

        self.table_dumps = QTableWidget(0, 3)
        self.table_dumps.setHorizontalHeaderLabels(["Arquivo de Despejo", "Tamanho", "Data de Modificação"])
        self.table_dumps.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_dumps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_dumps.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        lay.addWidget(self.table_dumps)

        self.tabs.addTab(tab, "Arquivos Minidump (.dmp)")

    def _setup_dictionary_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Pesquisar Código BugCheck (Hex ou Nome):"))
        self.txt_search_code = QLineEdit()
        self.txt_search_code.setPlaceholderText("Ex: 0x124, 0xD1, MEMORY, IRQL...")
        self.txt_search_code.textChanged.connect(self._filter_dictionary)
        search_bar.addWidget(self.txt_search_code)
        lay.addLayout(search_bar)

        self.table_dict = QTableWidget(0, 2)
        self.table_dict.setHorizontalHeaderLabels(["Código Hexadecimal", "Causa Provável e Significado"])
        self.table_dict.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_dict.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table_dict)

        # Preenche dicionário padrão
        self._populate_dictionary("")

        self.tabs.addTab(tab, "Dicionário de Códigos BSOD")

    def _populate_dictionary(self, query: str) -> None:
        q = query.lower().strip()
        items = []
        for code, desc in BUGCHECK_DESCRIPTIONS.items():
            hex_str = f"0x{code:08X}"
            if not q or q in hex_str.lower() or q in desc.lower():
                items.append((hex_str, desc))

        self.table_dict.setRowCount(len(items))
        for row, (h, d) in enumerate(items):
            self.table_dict.setItem(row, 0, QTableWidgetItem(h))
            self.table_dict.setItem(row, 1, QTableWidgetItem(d))

    def _filter_dictionary(self, text: str) -> None:
        self._populate_dictionary(text)

    def _open_minidump_folder(self) -> None:
        p = "C:\\Windows\\Minidump"
        if os.path.exists(p):
            os.startfile(p)
        else:
            show_toast(self, "A pasta C:\\Windows\\Minidump não existe (nenhum dump gravado ainda).")

    def _refresh_all_async(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Consultando logs do sistema e arquivos de despejo...")

        def _worker():
            evs = query_system_crash_events(50)
            dumps = list_minidump_files()
            return evs, dumps

        def _on_done(result):
            evs, dumps = result
            self.btn_refresh.setEnabled(True)
            self._events_cache = evs

            # Preenche eventos
            self.table_events.setRowCount(len(evs))
            for row, e in enumerate(evs):
                self.table_events.setItem(row, 0, QTableWidgetItem(e["time"]))
                self.table_events.setItem(row, 1, QTableWidgetItem(str(e["id"])))
                self.table_events.setItem(row, 2, QTableWidgetItem(e["category"]))
                self.table_events.setItem(row, 3, QTableWidgetItem(e["explanation"]))

            # Preenche dumps
            self.table_dumps.setRowCount(len(dumps))
            for row, d in enumerate(dumps):
                self.table_dumps.setItem(row, 0, QTableWidgetItem(d["name"]))
                self.table_dumps.setItem(row, 1, QTableWidgetItem(d["size_str"]))
                self.table_dumps.setItem(row, 2, QTableWidgetItem(d["modified"]))

            self.lbl_status.setText(f"{len(evs)} evento(s) de falha e {len(dumps)} arquivo(s) de dump encontrados.")

        def _on_error(err):
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText("Erro ao consultar logs de travamentos.")
            show_toast(self, "Falha na análise de travamentos", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _on_event_selected(self) -> None:
        row = self.table_events.currentRow()
        if row >= 0 and hasattr(self, "_events_cache") and row < len(self._events_cache):
            self.txt_detail.setText(self._events_cache[row]["raw_message"])
