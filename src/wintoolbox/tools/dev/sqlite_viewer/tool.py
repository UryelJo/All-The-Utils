"""
Interface gráfica do Visualizador de SQLite e Executor de Consultas SQL.
Utiliza DataTableView e RecordTableModel para alta escalabilidade e rolagem suave.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.dev.sqlite_viewer.logic import (
    execute_query, export_query_results, get_table_schema, list_tables_and_views
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("dev.sqlite_viewer.ui")


@register
class SqliteViewerTool(Tool):
    id = "dev.sqlite_viewer"
    name = "Visualizador de SQLite"
    category = "Desenvolvimento"
    description = "Inspeção somente-leitura de bancos SQLite locais, visualização de tabelas e executor de consultas SQL"
    keywords = ["sqlite", "sql", "banco", "dados", "tabela", "database", "query", "select", "dev"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SqliteViewerView(self, parent)


class SqliteViewerView(QWidget):
    def __init__(self, tool: SqliteViewerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_db_path: Optional[Path] = None
        self._current_records: List[Dict[str, Any]] = []
        self._task_runner: Optional[TaskRunner] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Visualizador de SQLite",
            "Abra com segurança bancos de dados locais em modo somente-leitura, consulte esquemas e execute queries."
        ))

        # Barra Superior de Arquivo
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.btn_open = QPushButton("Abrir Banco de Dados SQLite...")
        self.btn_open.setProperty("class", "primary")
        self.btn_open.clicked.connect(self._on_open_file)
        bar.addWidget(self.btn_open)

        self.lbl_path = QLabel("Nenhum banco de dados carregado.")
        self.lbl_path.setProperty("class", "secondary")
        bar.addWidget(self.lbl_path, stretch=1)

        root.addLayout(bar)

        # Splitter Principal: Esquerda = Tabelas / Direita = Visualizador + Editor SQL
        self.splitter = QSplitter(Qt.Horizontal)

        # ── Coluna Esquerda: Tabelas e Views ──
        left_widget = QFrame()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl_tables = QLabel("Tabelas e Visualizações:")
        lbl_tables.setStyleSheet("font-weight: 600; font-size: 12px;")
        left_layout.addWidget(lbl_tables)

        self.list_tables = QListWidget()
        self.list_tables.itemClicked.connect(self._on_table_selected)
        left_layout.addWidget(self.list_tables, stretch=1)

        self.splitter.addWidget(left_widget)

        # ── Coluna Direita: Abas de Dados, Consulta SQL e DDL ──
        right_widget = QFrame()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.tabs = QTabWidget()

        # Aba 1: Tabela de Dados
        self.tab_data = QWidget()
        l_data = QVBoxLayout(self.tab_data)
        l_data.setContentsMargins(4, 8, 4, 4)
        l_data.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtrar resultados visualizados...")
        self.txt_filter.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.txt_filter, stretch=1)

        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.clicked.connect(lambda: self._export_current("csv"))
        filter_row.addWidget(self.btn_export_csv)

        self.btn_export_json = QPushButton("Exportar JSON")
        self.btn_export_json.clicked.connect(lambda: self._export_current("json"))
        filter_row.addWidget(self.btn_export_json)

        l_data.addLayout(filter_row)

        self.table_container = QVBoxLayout()
        self.table_container.setContentsMargins(0, 0, 0, 0)
        self.table_view = DataTableView([Column("info", "Abra um banco para carregar colunas")])
        self.table_container.addWidget(self.table_view)
        l_data.addLayout(self.table_container, stretch=1)

        self.lbl_status = QLabel("Selecione uma tabela à esquerda.")
        self.lbl_status.setProperty("class", "secondary")
        l_data.addWidget(self.lbl_status)

        self.tabs.addTab(self.tab_data, "Dados da Tabela")

        # Aba 2: Editor de Consultas SQL
        self.tab_sql = QWidget()
        l_sql = QVBoxLayout(self.tab_sql)
        l_sql.setContentsMargins(4, 8, 4, 4)
        l_sql.setSpacing(8)

        self.txt_sql = QTextEdit()
        self.txt_sql.setFont(QFont("Cascadia Mono, Consolas, Courier New", 10))
        self.txt_sql.setPlaceholderText("Digite uma consulta SQL (ex: SELECT * FROM tabela WHERE ...) e clique em Executar")
        self.txt_sql.setMaximumHeight(130)
        l_sql.addWidget(self.txt_sql)

        btn_row = QHBoxLayout()
        self.btn_run_sql = QPushButton("Executar Consulta SQL")
        self.btn_run_sql.setProperty("class", "primary")
        self.btn_run_sql.clicked.connect(self._on_execute_custom_sql)
        btn_row.addWidget(self.btn_run_sql)
        btn_row.addStretch()
        l_sql.addLayout(btn_row)

        self.sql_result_container = QVBoxLayout()
        self.sql_table_view = DataTableView([Column("info", "Execute uma consulta para visualizar os resultados")])
        self.sql_result_container.addWidget(self.sql_table_view)
        l_sql.addLayout(self.sql_result_container, stretch=1)

        self.lbl_sql_status = QLabel("Pronto.")
        self.lbl_sql_status.setProperty("class", "secondary")
        l_sql.addWidget(self.lbl_sql_status)

        self.tabs.addTab(self.tab_sql, "Editor de Consultas SQL")

        # Aba 3: Esquema e DDL
        self.tab_ddl = QWidget()
        l_ddl = QVBoxLayout(self.tab_ddl)
        l_ddl.setContentsMargins(4, 8, 4, 4)
        self.txt_ddl = QTextEdit()
        self.txt_ddl.setReadOnly(True)
        self.txt_ddl.setFont(QFont("Cascadia Mono, Consolas, Courier New", 10))
        l_ddl.addWidget(self.txt_ddl)
        self.tabs.addTab(self.tab_ddl, "Esquema / DDL")

        right_layout.addWidget(self.tabs)
        self.splitter.addWidget(right_widget)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        root.addWidget(self.splitter, stretch=1)

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Banco de Dados SQLite",
            "",
            "Bancos SQLite (*.db *.sqlite *.sqlite3 *.db3);;Todos os Arquivos (*.*)"
        )
        if not path:
            return
        self.load_database(Path(path))

    def load_database(self, path: Path) -> None:
        self._current_db_path = path
        self.lbl_path.setText(str(path))
        self.list_tables.clear()

        try:
            items = list_tables_and_views(path)
            for it in items:
                count_str = f"{it['count']:,} linhas" if it['count'] >= 0 else "view"
                item = QListWidgetItem(f"{it['name']} ({count_str})")
                item.setData(Qt.UserRole, it)
                self.list_tables.addItem(item)

            show_toast(self, "Banco Carregado", f"{len(items)} tabela(s) e visualizações detectadas.", kind="success")
            if items:
                self.list_tables.setCurrentRow(0)
                self._on_table_selected(self.list_tables.item(0))
        except Exception as e:
            _log.exception("Falha ao abrir banco %s", path)
            show_toast(self, "Erro ao Abrir", str(e), kind="error")

    def _on_table_selected(self, item: Optional[QListWidgetItem]) -> None:
        if not item or not self._current_db_path:
            return
        meta = item.data(Qt.UserRole) or {}
        tbl_name = meta.get("name", "")
        self.txt_ddl.setPlainText(meta.get("ddl", "") or f"-- Sem DDL disponível para {tbl_name}")
        self.txt_sql.setPlainText(f"SELECT * FROM [{tbl_name}] LIMIT 500;")

        # Carrega os dados da tabela
        self._run_query_internal(f"SELECT * FROM [{tbl_name}] LIMIT 500;", target_view="table")

    def _on_execute_custom_sql(self) -> None:
        sql = self.txt_sql.toPlainText().strip()
        if not sql:
            show_toast(self, "Aviso", "Digite uma consulta SQL.", kind="warning")
            return
        self._run_query_internal(sql, target_view="sql")

    def _run_query_internal(self, sql: str, target_view: str = "table") -> None:
        if not self._current_db_path:
            return

        try:
            cols, records, elapsed = execute_query(self._current_db_path, sql, max_rows=1000)
            self._current_records = records

            # Monta novo DataTableView com as colunas dinâmicas
            table_cols = [Column(key=c, title=c) for c in cols]
            if not table_cols:
                table_cols = [Column("status", "Nenhum resultado")]

            new_view = DataTableView(table_cols)
            new_view.set_records(records)

            if target_view == "table":
                # Substitui a visualização de dados
                while self.table_container.count():
                    old = self.table_container.takeAt(0)
                    if old.widget():
                        old.widget().deleteLater()
                self.table_view = new_view
                self.table_container.addWidget(self.table_view)
                self.lbl_status.setText(f"{len(records):,} linha(s) em {elapsed*1000:.1f} ms")
            else:
                while self.sql_result_container.count():
                    old = self.sql_result_container.takeAt(0)
                    if old.widget():
                        old.widget().deleteLater()
                self.sql_table_view = new_view
                self.sql_result_container.addWidget(self.sql_table_view)
                self.lbl_sql_status.setText(f"{len(records):,} linha(s) retornada(s) em {elapsed*1000:.1f} ms")

            # Aplica filtro se houver
            if self.txt_filter.text():
                new_view.proxy.set_text_filter(self.txt_filter.text())

        except Exception as e:
            _log.warning("Erro na consulta SQL: %s", e)
            show_toast(self, "Erro SQL", str(e), kind="error")
            if target_view == "sql":
                self.lbl_sql_status.setText(f"Erro: {e}")

    def _on_filter_changed(self, text: str) -> None:
        if hasattr(self, "table_view") and hasattr(self.table_view, "proxy"):
            self.table_view.proxy.set_text_filter(text)
        if hasattr(self, "sql_table_view") and hasattr(self.sql_table_view, "proxy"):
            self.sql_table_view.proxy.set_text_filter(text)

    def _export_current(self, fmt: str) -> None:
        if not self._current_records:
            show_toast(self, "Aviso", "Nenhum dado carregado para exportar.", kind="warning")
            return
        content = export_query_results(self._current_records, format_type=fmt)
        ext = ".csv" if fmt == "csv" else ".json"
        filter_str = "Arquivo CSV (*.csv)" if fmt == "csv" else "Arquivo JSON (*.json)"

        path, _ = QFileDialog.getSaveFileName(self, f"Exportar Resultados ({fmt.upper()})", f"sqlite_export{ext}", filter_str)
        if path:
            Path(path).write_text(content, encoding="utf-8")
            show_toast(self, "Exportado", f"Arquivo salvo com sucesso em:\n{path}", kind="success")
