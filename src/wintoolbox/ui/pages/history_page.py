"""
Página de Histórico de Tarefas (History Page).
Exibe resumo estatístico de execuções, busca rápida e tabela interativa
das tarefas registradas no SQLite com atalho para reabrir a ferramenta.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.history import clear_history, get_recent_jobs
from wintoolbox.core.registry import get_tool
from wintoolbox.ui.icons import normalize_text
from wintoolbox.ui.widgets.toast import show_toast


class HistoryPage(QWidget):
    """Visualizador do histórico de tarefas executadas."""
    tool_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._jobs_cache: List[Dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 24)
        root_layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel("Histórico de Tarefas e Execuções")
        lbl_title.setProperty("class", "title")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel("Registro local em SQLite de todos os processamentos em lote e tarefas executadas.")
        lbl_desc.setProperty("class", "secondary")
        root_layout.addWidget(lbl_desc)

        # Cartões de Resumo Estatístico
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.lbl_stat_jobs = self._create_stat_card(stats_row, "Total de Tarefas", "0")
        self.lbl_stat_items = self._create_stat_card(stats_row, "Arquivos Processados", "0")
        self.lbl_stat_rate = self._create_stat_card(stats_row, "Taxa de Sucesso", "100%")

        root_layout.addLayout(stats_row)

        # Barra de ferramentas da tabela
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(8)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtrar histórico por ferramenta, status ou mensagem...")
        self.txt_filter.setMinimumWidth(280)
        self.txt_filter.textChanged.connect(self._render_filtered)
        tb_layout.addWidget(self.txt_filter)

        tb_layout.addStretch()

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.clicked.connect(self.refresh)
        tb_layout.addWidget(btn_refresh)

        btn_clear = QPushButton("Limpar Histórico")
        btn_clear.clicked.connect(self._on_clear)
        tb_layout.addWidget(btn_clear)

        root_layout.addLayout(tb_layout)

        # Tabela (6 colunas originais + botão de ação)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Data/Hora", "Ferramenta", "Status", "Itens", "Duração", "Mensagem", "Ação"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        root_layout.addWidget(self.table, stretch=1)

    def _create_stat_card(self, parent_layout: QHBoxLayout, label_title: str, initial_val: str) -> QLabel:
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QVBoxLayout(card)
        l_card.setContentsMargins(16, 12, 16, 12)
        l_card.setSpacing(2)

        lbl_cap = QLabel(label_title)
        lbl_cap.setProperty("class", "secondary")
        l_card.addWidget(lbl_cap)

        lbl_val = QLabel(initial_val)
        lbl_val.setStyleSheet("font-size: 18px; font-weight: 700;")
        l_card.addWidget(lbl_val)

        parent_layout.addWidget(card, stretch=1)
        return lbl_val

    def refresh(self) -> None:
        self._jobs_cache = get_recent_jobs(limit=100)
        total_jobs = len(self._jobs_cache)
        total_items = sum(int(j.get("items_success", 0)) for j in self._jobs_cache)
        ok_jobs = sum(1 for j in self._jobs_cache if "sucesso" in str(j.get("status", "")).lower())
        rate = int((ok_jobs / total_jobs) * 100) if total_jobs > 0 else 100

        self.lbl_stat_jobs.setText(str(total_jobs))
        self.lbl_stat_items.setText(str(total_items))
        self.lbl_stat_rate.setText(f"{rate}%")

        self._render_filtered()

    def _render_filtered(self) -> None:
        q = normalize_text(self.txt_filter.text())
        filtered = []
        for j in self._jobs_cache:
            t = get_tool(j["tool_id"])
            t_name = t.name if t else j["tool_id"]
            if not q:
                filtered.append((j, t_name))
            else:
                hay = normalize_text(f"{t_name} {j.get('status', '')} {j.get('message', '')}")
                if q in hay:
                    filtered.append((j, t_name))

        self.table.setRowCount(len(filtered))
        for row, (j, t_name) in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(j["timestamp"]))
            self.table.setItem(row, 1, QTableWidgetItem(t_name))
            self.table.setItem(row, 2, QTableWidgetItem(j["status"]))

            itens_str = f"{j['items_success']}/{j['items_total']}"
            if j["items_failed"] > 0:
                itens_str += f" ({j['items_failed']} erros)"
            self.table.setItem(row, 3, QTableWidgetItem(itens_str))
            self.table.setItem(row, 4, QTableWidgetItem(f"{j['duration_sec']:.1f}s"))
            self.table.setItem(row, 5, QTableWidgetItem(j.get("message", "") or ""))

            tid = j["tool_id"]
            btn_open = QPushButton("Abrir")
            btn_open.setStyleSheet("padding: 2px 10px; font-size: 11px; min-height: 20px;")
            btn_open.clicked.connect(lambda _, tool_id=tid: self.tool_requested.emit(tool_id))
            self.table.setCellWidget(row, 6, btn_open)

    def _on_clear(self) -> None:
        clear_history()
        self.refresh()
        show_toast(self, "Histórico Limpo", "Todos os registros foram removidos.", kind="info")
