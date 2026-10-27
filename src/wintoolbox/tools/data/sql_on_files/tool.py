"""
Interface gráfica Fluent para consulta SQL em arquivos tabulares (CSV, JSON).
Permite importar múltiplos arquivos para um banco SQLite em memória e executar
consultas analíticas com exportação em múltiplos formatos.
"""
import sqlite3
from typing import Any, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.sql_on_files.logic import (
    execute_sql_query,
    export_query_results,
    import_csv_to_sqlite,
    import_json_to_sqlite,
)


@register
class SqlOnFilesTool(Tool):
    id = "data.sql_on_files"
    name = "SQL em Arquivos"
    description = "Carregue arquivos CSV e JSON para um banco SQLite em memória e execute consultas SQL analíticas."
    category = "Dados e Estruturas"
    icon = "Database"
    tags = ["sql", "sqlite", "csv", "json", "tabela", "consulta", "analise"]

    def __init__(self) -> None:
        super().__init__()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._loaded_tables: List[dict] = []
        self._last_columns: List[str] = []
        self._last_rows: List[List[Any]] = []

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra superior com ações de importação
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_add_csv = QPushButton("Importar CSV...")
        btn_add_json = QPushButton("Importar JSON...")
        btn_reset_db = QPushButton("Limpar Banco em Memória")

        top_bar.addWidget(btn_add_csv)
        top_bar.addWidget(btn_add_json)
        top_bar.addWidget(btn_reset_db)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        # Splitter Vertical: Painel de Tabelas/SQL no topo, Resultados embaixo
        v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Painel Superior: Tabelas carregadas (esquerda) + Editor SQL (direita)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lado esquerdo: Tabelas
        tables_widget = QWidget()
        tables_layout = QVBoxLayout(tables_widget)
        tables_layout.setContentsMargins(0, 0, 0, 0)
        tables_layout.setSpacing(6)
        tables_layout.addWidget(QLabel("Tabelas Carregadas no Banco:"))
        self.list_tables = QListWidget()
        tables_layout.addWidget(self.list_tables)

        h_splitter.addWidget(tables_widget)

        # Lado direito: Editor SQL
        sql_widget = QWidget()
        sql_layout = QVBoxLayout(sql_widget)
        sql_layout.setContentsMargins(0, 0, 0, 0)
        sql_layout.setSpacing(6)

        sql_header = QHBoxLayout()
        sql_header.addWidget(QLabel("Consulta SQL (SQLite):"))
        sql_header.addStretch()

        btn_sample_query = QPushButton("SELECT * LIMIT 50")
        btn_count_query = QPushButton("COUNT(*)")
        btn_execute = QPushButton("Executar Consulta (F5)")
        btn_execute.setStyleSheet("font-weight: bold;")

        sql_header.addWidget(btn_sample_query)
        sql_header.addWidget(btn_count_query)
        sql_header.addWidget(btn_execute)
        sql_layout.addLayout(sql_header)

        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("Escreva sua consulta SQL aqui (ex: SELECT * FROM nome_tabela)...")
        sql_layout.addWidget(self.sql_editor)

        h_splitter.addWidget(sql_widget)
        h_splitter.setSizes([260, 640])

        v_splitter.addWidget(h_splitter)

        # Painel Inferior: Resultados
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(6)

        results_header = QHBoxLayout()
        self.lbl_query_status = QLabel("Nenhuma consulta executada.")
        results_header.addWidget(self.lbl_query_status)
        results_header.addStretch()

        btn_copy_csv = QPushButton("Copiar como CSV")
        btn_copy_md = QPushButton("Copiar Markdown")
        btn_save_json = QPushButton("Exportar JSON...")

        results_header.addWidget(btn_copy_csv)
        results_header.addWidget(btn_copy_md)
        results_header.addWidget(btn_save_json)
        results_layout.addLayout(results_header)

        self.table_results = QTableWidget()
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        results_layout.addWidget(self.table_results)

        v_splitter.addWidget(results_widget)
        v_splitter.setSizes([320, 380])

        layout.addWidget(v_splitter, 1)

        # Conexões
        btn_add_csv.clicked.connect(self._on_import_csv)
        btn_add_json.clicked.connect(self._on_import_json)
        btn_reset_db.clicked.connect(self._on_reset_db)
        btn_execute.clicked.connect(self._on_execute_query)
        btn_sample_query.clicked.connect(self._on_quick_sample)
        btn_count_query.clicked.connect(self._on_quick_count)
        btn_copy_csv.clicked.connect(self._on_copy_csv)
        btn_copy_md.clicked.connect(self._on_copy_md)
        btn_save_json.clicked.connect(self._on_save_json)
        self.list_tables.itemDoubleClicked.connect(self._on_table_double_clicked)

        return container

    def _on_import_csv(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(None, "Importar Arquivos CSV", "", "Arquivos CSV (*.csv *.tsv *.txt);;Todos os Arquivos (*.*)")
        for file_path in files:
            try:
                res = import_csv_to_sqlite(self._conn, file_path)
                self._loaded_tables.append(res)
                self.list_tables.addItem(f"{res['table_name']} ({res['row_count']} linhas, {len(res['columns'])} cols)")
                if not self.sql_editor.toPlainText().strip():
                    self.sql_editor.setPlainText(f"SELECT * FROM {res['table_name']} LIMIT 50;")
            except Exception as exc:
                QMessageBox.critical(None, "Erro ao Importar CSV", f"Falha no arquivo {file_path}:\n{exc}")

    def _on_import_json(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(None, "Importar Arquivos JSON", "", "Arquivos JSON (*.json);;Todos os Arquivos (*.*)")
        for file_path in files:
            try:
                res = import_json_to_sqlite(self._conn, file_path)
                self._loaded_tables.append(res)
                self.list_tables.addItem(f"{res['table_name']} ({res['row_count']} linhas, {len(res['columns'])} cols)")
                if not self.sql_editor.toPlainText().strip():
                    self.sql_editor.setPlainText(f"SELECT * FROM {res['table_name']} LIMIT 50;")
            except Exception as exc:
                QMessageBox.critical(None, "Erro ao Importar JSON", f"Falha no arquivo {file_path}:\n{exc}")

    def _on_reset_db(self) -> None:
        self._conn.close()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._loaded_tables.clear()
        self.list_tables.clear()
        self.table_results.clear()
        self.table_results.setRowCount(0)
        self.table_results.setColumnCount(0)
        self.lbl_query_status.setText("Banco de dados em memória limpo com sucesso.")

    def _get_active_table_name(self) -> str:
        current_item = self.list_tables.currentItem()
        if current_item:
            return current_item.text().split()[0]
        if self._loaded_tables:
            return self._loaded_tables[0]["table_name"]
        return "tabela"

    def _on_quick_sample(self) -> None:
        tbl = self._get_active_table_name()
        self.sql_editor.setPlainText(f"SELECT * FROM {tbl} LIMIT 50;")
        self._on_execute_query()

    def _on_quick_count(self) -> None:
        tbl = self._get_active_table_name()
        self.sql_editor.setPlainText(f"SELECT COUNT(*) AS total_linhas FROM {tbl};")
        self._on_execute_query()

    def _on_table_double_clicked(self) -> None:
        self._on_quick_sample()

    def _on_execute_query(self) -> None:
        query = self.sql_editor.toPlainText().strip()
        if not query:
            return

        res = execute_sql_query(self._conn, query)
        if res["error"]:
            self.lbl_query_status.setText(f"❌ Erro SQL: {res['error']}")
            QMessageBox.warning(None, "Erro na Consulta", res["error"])
            return

        cols = res["columns"]
        rows = res["rows"]
        self._last_columns = cols
        self._last_rows = rows

        self.table_results.clear()
        self.table_results.setColumnCount(len(cols))
        self.table_results.setHorizontalHeaderLabels(cols)
        self.table_results.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            for col_idx, cell_value in enumerate(row_data):
                self.table_results.setItem(row_idx, col_idx, QTableWidgetItem(str(cell_value)))

        self.lbl_query_status.setText(
            f"✅ Consulta executada em {res['elapsed_ms']} ms. {res['row_count']} linha(s) retornada(s)."
        )

    def _on_copy_csv(self) -> None:
        if not self._last_columns:
            return
        csv_str = export_query_results(self._last_columns, self._last_rows, "csv")
        QApplication.clipboard().setText(csv_str)
        self.lbl_query_status.setText("Resultado copiado para a área de transferência no formato CSV.")

    def _on_copy_md(self) -> None:
        if not self._last_columns:
            return
        md_str = export_query_results(self._last_columns, self._last_rows, "markdown")
        QApplication.clipboard().setText(md_str)
        self.lbl_query_status.setText("Resultado copiado para a área de transferência no formato Markdown.")

    def _on_save_json(self) -> None:
        if not self._last_columns:
            return
        file_path, _ = QFileDialog.getSaveFileName(None, "Exportar Consulta JSON", "resultado.json", "Arquivos JSON (*.json)")
        if not file_path:
            return
        try:
            json_str = export_query_results(self._last_columns, self._last_rows, "json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            self.lbl_query_status.setText(f"Exportado com sucesso para {file_path}")
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Exportar", str(exc))
