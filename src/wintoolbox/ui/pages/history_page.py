"""
Página de Histórico de Tarefas (History Page).
Exibe execuções anteriores registradas no SQLite.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.history import clear_history, get_recent_jobs
from wintoolbox.core.registry import get_tool

class HistoryPage(QWidget):
    """Visualizador do histórico de tarefas executadas."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel("Histórico de Tarefas")
        lbl_title.setProperty("class", "title")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel("Registro das operações e lotes executados no sistema.")
        lbl_desc.setProperty("class", "secondary")
        root_layout.addWidget(lbl_desc)

        # Barra de ferramentas da tabela
        tb_layout = QHBoxLayout()
        btn_refresh = QPushButton("Atualizar")
        btn_refresh.clicked.connect(self.refresh)
        tb_layout.addWidget(btn_refresh)

        btn_clear = QPushButton("Limpar Histórico")
        btn_clear.clicked.connect(self._on_clear)
        tb_layout.addWidget(btn_clear)

        tb_layout.addStretch()
        root_layout.addLayout(tb_layout)

        # Tabela
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Data/Hora", "Ferramenta", "Status", "Itens", "Duração", "Mensagem"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root_layout.addWidget(self.table)

    def refresh(self):
        jobs = get_recent_jobs(limit=100)
        self.table.setRowCount(len(jobs))
        for row, j in enumerate(jobs):
            # Data
            self.table.setItem(row, 0, QTableWidgetItem(j["timestamp"]))

            # Nome da ferramenta
            t = get_tool(j["tool_id"])
            t_name = t.name if t else j["tool_id"]
            self.table.setItem(row, 1, QTableWidgetItem(t_name))

            # Status
            self.table.setItem(row, 2, QTableWidgetItem(j["status"]))

            # Itens
            itens_str = f"{j['items_success']}/{j['items_total']}"
            if j["items_failed"] > 0:
                itens_str += f" ({j['items_failed']} erros)"
            self.table.setItem(row, 3, QTableWidgetItem(itens_str))

            # Duração
            self.table.setItem(row, 4, QTableWidgetItem(f"{j['duration_sec']:.1f}s"))

            # Mensagem
            self.table.setItem(row, 5, QTableWidgetItem(j.get("message", "") or ""))

    def _on_clear(self):
        clear_history()
        self.refresh()
