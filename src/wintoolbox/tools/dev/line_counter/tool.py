"""
Interface de usuário para a ferramenta Contador de Linhas de Código (CLOC).
"""
import csv
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.line_counter.logic import (
    CodeMarker,
    FileStats,
    LanguageStats,
    count_project_lines,
)


@register
class LineCounterTool(Tool):
    """Contador de linhas de código-fonte por linguagem com levantamento de TODO e FIXME."""

    id = "dev.line_counter"
    name = "Contador de Linhas de Código (CLOC)"
    description = "Analisa repositórios de código quantificando linhas efetivas, comentários, linhas vazias e marcações TODO/FIXME por linguagem."
    category = "Desenvolvimento"

    def __init__(self):
        super().__init__()
        self.current_languages: Dict[str, LanguageStats] = {}
        self.current_files: List[FileStats] = []
        self.current_markers: List[CodeMarker] = []

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Contador de Linhas de Código (CLOC)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Métricas estruturais de código-fonte: linhas de código efetivo (SLOC), "
            "comentários, espaçamento e inventário de anotações técnicas."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Painel de Seleção
        top_frame = QFrame()
        top_frame.setFrameShape(QFrame.Shape.StyledPanel)
        top_layout = QHBoxLayout(top_frame)

        self.txt_dir = QLineEdit()
        self.txt_dir.setPlaceholderText("Selecione a pasta do repositório ou projeto...")
        self.btn_browse = QPushButton("Procurar...")
        self.btn_browse.clicked.connect(self._browse)

        self.btn_count = QPushButton("Analisar Linhas")
        self.btn_count.setStyleSheet("font-weight: bold;")
        self.btn_count.clicked.connect(self._analyze)

        top_layout.addWidget(self.txt_dir, 1)
        top_layout.addWidget(self.btn_browse)
        top_layout.addWidget(self.btn_count)
        layout.addWidget(top_frame)

        # Abas de Análise
        self.tabs = QTabWidget()

        # Aba 1: Linguagens
        self.table_langs = QTableWidget()
        self.table_langs.setColumnCount(7)
        self.table_langs.setHorizontalHeaderLabels([
            "Linguagem", "Arquivos", "Linhas de Código", "Comentários", "Linhas Vazias", "Total", "% Código"
        ])
        self.table_langs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_langs, "Visão Geral por Linguagem")

        # Aba 2: Arquivos
        self.table_files = QTableWidget()
        self.table_files.setColumnCount(6)
        self.table_files.setHorizontalHeaderLabels([
            "Arquivo", "Linguagem", "Código", "Comentários", "Vazias", "Total"
        ])
        self.table_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_files, "Arquivos Individuais")

        # Aba 3: Tarefas (TODO / FIXME)
        self.table_markers = QTableWidget()
        self.table_markers.setColumnCount(4)
        self.table_markers.setHorizontalHeaderLabels(["Tipo", "Linha", "Arquivo", "Descrição"])
        self.table_markers.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_markers, "Anotações (TODO / FIXME)")

        layout.addWidget(self.tabs, 1)

        # Barra de Resumo e Exportação
        b_frame = QFrame()
        b_layout = QHBoxLayout(b_frame)
        b_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_summary = QLabel("Nenhum projeto analisado.")
        self.lbl_summary.setStyleSheet("font-weight: bold; color: #2196f3;")

        self.btn_export_csv = QPushButton("Exportar Relatório CSV...")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self._export_csv)

        b_layout.addWidget(self.lbl_summary)
        b_layout.addStretch()
        b_layout.addWidget(self.btn_export_csv)
        layout.addWidget(b_frame)

        return widget

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Diretório do Projeto")
        if folder:
            self.txt_dir.setText(folder)

    def _analyze(self):
        raw = self.txt_dir.text().strip()
        if not raw:
            QMessageBox.warning(None, "Aviso", "Selecione uma pasta para analisar.")
            return

        target_dir = Path(raw)
        if not target_dir.is_dir():
            QMessageBox.critical(None, "Erro", "O diretório informado não existe.")
            return

        self.btn_count.setEnabled(False)
        self.lbl_summary.setText("Contando linhas de código... Por favor aguarde.")

        try:
            langs, files, markers = count_project_lines(target_dir)
            self.current_languages = langs
            self.current_files = files
            self.current_markers = markers

            self._populate_views(langs, files, markers)
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha na análise: {e}")
            self.lbl_summary.setText("Erro na análise.")
        finally:
            self.btn_count.setEnabled(True)

    def _populate_views(
        self,
        langs: Dict[str, LanguageStats],
        files: List[FileStats],
        markers: List[CodeMarker]
    ):
        # 1. Tabela de Linguagens
        sorted_langs = sorted(langs.values(), key=lambda l: l.lines_code, reverse=True)
        self.table_langs.setRowCount(len(sorted_langs))

        tot_files = 0
        tot_code = 0
        tot_comments = 0
        tot_blank = 0
        tot_all = 0

        for row, l in enumerate(sorted_langs):
            tot_files += l.files_count
            tot_code += l.lines_code
            tot_comments += l.lines_comment
            tot_blank += l.lines_blank
            tot_all += l.total_lines

            pct = (l.lines_code / l.total_lines * 100) if l.total_lines > 0 else 0.0

            self.table_langs.setItem(row, 0, QTableWidgetItem(l.language))
            self.table_langs.setItem(row, 1, QTableWidgetItem(f"{l.files_count:,}"))
            self.table_langs.setItem(row, 2, QTableWidgetItem(f"{l.lines_code:,}"))
            self.table_langs.setItem(row, 3, QTableWidgetItem(f"{l.lines_comment:,}"))
            self.table_langs.setItem(row, 4, QTableWidgetItem(f"{l.lines_blank:,}"))
            self.table_langs.setItem(row, 5, QTableWidgetItem(f"{l.total_lines:,}"))
            self.table_langs.setItem(row, 6, QTableWidgetItem(f"{pct:.1f}%"))

        # 2. Tabela de Arquivos
        sorted_files = sorted(files, key=lambda f: f.lines_code, reverse=True)
        self.table_files.setRowCount(len(sorted_files))
        for row, f in enumerate(sorted_files):
            self.table_files.setItem(row, 0, QTableWidgetItem(f.path.name))
            self.table_files.setItem(row, 1, QTableWidgetItem(f.language))
            self.table_files.setItem(row, 2, QTableWidgetItem(f"{f.lines_code:,}"))
            self.table_files.setItem(row, 3, QTableWidgetItem(f"{f.lines_comment:,}"))
            self.table_files.setItem(row, 4, QTableWidgetItem(f"{f.lines_blank:,}"))
            self.table_files.setItem(row, 5, QTableWidgetItem(f"{f.total_lines:,}"))

        # 3. Tabela de Tarefas
        self.table_markers.setRowCount(len(markers))
        for row, m in enumerate(markers):
            it_type = QTableWidgetItem(m.marker_type)
            if m.marker_type == "FIXME":
                it_type.setForeground(Qt.GlobalColor.red)
            else:
                it_type.setForeground(Qt.GlobalColor.darkYellow)

            self.table_markers.setItem(row, 0, it_type)
            self.table_markers.setItem(row, 1, QTableWidgetItem(str(m.line_number)))
            self.table_markers.setItem(row, 2, QTableWidgetItem(m.file_path.name))
            self.table_markers.setItem(row, 3, QTableWidgetItem(m.content))

        self.lbl_summary.setText(
            f"Total: {tot_files:,} arquivos | {tot_code:,} linhas de código | "
            f"{tot_comments:,} comentários | {len(markers)} anotações encontradas"
        )
        self.btn_export_csv.setEnabled(len(files) > 0)

    def _export_csv(self):
        if not self.current_languages:
            return

        dest, _ = QFileDialog.getSaveFileName(
            None, "Exportar Relatório CSV", "contagem_linhas.csv", "Arquivos CSV (*.csv)"
        )
        if not dest:
            return

        try:
            with open(dest, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow([
                    "Linguagem", "Arquivos", "Linhas de Código", "Comentários", "Linhas Vazias", "Total"
                ])
                for l in self.current_languages.values():
                    writer.writerow([
                        l.language, l.files_count, l.lines_code, l.lines_comment, l.lines_blank, l.total_lines
                    ])
            QMessageBox.information(None, "Exportado", f"Relatório salvo em: {dest}")
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha ao exportar CSV: {e}")
