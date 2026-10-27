"""
Interface gráfica da ferramenta Conversor de CSV para Banco de Dados e SQL (data.csv_to_db).
Permite importar arquivos CSV, TSV e DSV, inferir tipos de dados automaticamente,
gravar diretamente em bancos SQLite físicos (.db) e gerar scripts SQL com transações.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.data.csv_to_db.logic import (
    csv_to_sql_script,
    csv_to_sqlite,
    read_csv_data,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class CsvToDbTool(Tool):
    id = "data.csv_to_db"
    name = "Conversor de CSV para Banco SQLite e SQL"
    category = "Dados e Estruturas"
    description = (
        "Converte arquivos CSV/TSV para bancos de dados SQLite físicos e gera scripts SQL de migração "
        "com inferência automática de tipos de dados (INTEGER, REAL, DATE, TEXT)."
    )
    keywords = ["csv", "sqlite", "sql", "db", "tabela", "banco de dados", "tsv", "migracao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CsvToDbView(self, parent)


class CsvToDbView(QWidget):
    def __init__(self, tool: CsvToDbTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._selected_csv_path: Optional[Path] = None
        self._schema_data = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Barra Superior: Seleção de Arquivo e Delimitador
        top_bar = QHBoxLayout()
        self._txt_file_path = QLineEdit()
        self._txt_file_path.setPlaceholderText("Selecione um arquivo CSV, TSV ou DSV...")
        self._txt_file_path.setReadOnly(True)
        top_bar.addWidget(self._txt_file_path)

        btn_browse = QPushButton("Abrir Arquivo...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_bar.addWidget(btn_browse)

        top_bar.addWidget(QLabel("Delimitador:"))
        self._combo_delim = QComboBox()
        self._combo_delim.addItem("Auto-detectar", "")
        self._combo_delim.addItem("Vírgula (,)", ",")
        self._combo_delim.addItem("Ponto e Vírgula (;)", ";")
        self._combo_delim.addItem("Tabulação (\\t)", "\t")
        self._combo_delim.addItem("Pipe (|)", "|")
        self._combo_delim.currentIndexChanged.connect(self._reload_csv_preview)
        top_bar.addWidget(self._combo_delim)

        top_bar.addWidget(QLabel("Tabela:"))
        self._txt_table_name = QLineEdit("clientes")
        self._txt_table_name.setFixedWidth(120)
        top_bar.addWidget(self._txt_table_name)

        root_layout.addLayout(top_bar)

        self._lbl_status = QLabel("Nenhum arquivo carregado.")
        self._lbl_status.setStyleSheet("color: #4b5563; font-weight: bold; font-size: 11px;")
        root_layout.addWidget(self._lbl_status)

        # Abas Centrais: Esquema Inferido & Pré-visualização do Script SQL
        self._tabs = QTabWidget()

        # Aba 1: Esquema Inferido
        cols = [
            Column("column_name", "Coluna SQL", width=160),
            Column("type", "Tipo Inferido", width=120),
            Column("original_name", "Cabeçalho Original", width=160),
            Column("sample", "Amostra dos Dados", width=320),
        ]
        self._schema_table = DataTableView(cols, key="column_name", parent=self)
        self._tabs.addTab(self._schema_table, "Esquema Inferido e Tipos")

        # Aba 2: Script SQL Gerado
        self._txt_sql_script = QPlainTextEdit()
        self._txt_sql_script.setFont(QFont("Consolas", 9))
        self._txt_sql_script.setReadOnly(True)
        self._tabs.addTab(self._txt_sql_script, "Script SQL (.sql)")

        root_layout.addWidget(self._tabs)

        # Barra de Ações Inferior
        act_bar = QHBoxLayout()
        btn_export_db = QPushButton("Exportar Diretamente para SQLite (.db)...")
        btn_export_db.clicked.connect(self._on_export_sqlite)
        act_bar.addWidget(btn_export_db)

        btn_gen_sql = QPushButton("Gerar e Visualizar Script SQL")
        btn_gen_sql.clicked.connect(self._on_generate_sql)
        act_bar.addWidget(btn_gen_sql)

        btn_copy_sql = QPushButton("Copiar Script SQL")
        btn_copy_sql.clicked.connect(self._copy_sql_script)
        act_bar.addWidget(btn_copy_sql)

        act_bar.addStretch()
        root_layout.addLayout(act_bar)

    def _on_browse_file(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo CSV / TSV", "", "Arquivos Tabulares (*.csv *.tsv *.txt *.dsv);;Todos (*.*)"
        )
        if not fpath:
            return
        self._selected_csv_path = Path(fpath)
        self._txt_file_path.setText(str(self._selected_csv_path))
        # Sugere nome de tabela baseado no nome do arquivo
        suggested_name = self._selected_csv_path.stem
        self._txt_table_name.setText(suggested_name)
        self._reload_csv_preview()

    def _reload_csv_preview(self):
        if not self._selected_csv_path or not self._selected_csv_path.is_file():
            return

        delim = self._combo_delim.currentData()
        try:
            headers, rows, schema = read_csv_data(self._selected_csv_path, delimiter=delim or None)
            self._schema_data = schema
            self._schema_table.set_records(schema)
            self._lbl_status.setText(
                f"Arquivo carregado com sucesso: {len(headers)} colunas e {len(rows)} linhas identificadas."
            )
        except Exception as exc:
            self._lbl_status.setText(f"Erro ao ler CSV: {exc}")

    def _on_export_sqlite(self):
        if not self._selected_csv_path:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione um arquivo CSV primeiro.")
            return

        db_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Banco SQLite", f"{self._txt_table_name.text()}.db", "Banco SQLite (*.db *.sqlite);;Todos (*.*)"
        )
        if not db_path:
            return

        delim = self._combo_delim.currentData()
        tname = self._txt_table_name.text().strip() or "tabela"

        try:
            res = csv_to_sqlite(self._selected_csv_path, Path(db_path), table_name=tname, delimiter=delim or None)
            QMessageBox.information(
                self,
                "Sucesso",
                f"Banco SQLite criado com sucesso!\n\nTabela: {res['table_name']}\nLinhas gravadas: {res['total_rows']}\nColunas: {res['total_columns']}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro de Conversão", f"Falha ao gerar banco SQLite: {exc}")

    def _on_generate_sql(self):
        if not self._selected_csv_path:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione um arquivo CSV primeiro.")
            return

        delim = self._combo_delim.currentData()
        tname = self._txt_table_name.text().strip() or "tabela"
        sql_text = csv_to_sql_script(self._selected_csv_path, table_name=tname, delimiter=delim or None)
        self._txt_sql_script.setPlainText(sql_text)
        self._tabs.setCurrentIndex(1)  # Alterna para a aba do script

    def _copy_sql_script(self):
        txt = self._txt_sql_script.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
