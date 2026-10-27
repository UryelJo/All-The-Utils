"""
Interface gráfica da ferramenta Extrator em Lote de Arquivos Compactados (archive.multi_extract).
Permite selecionar múltiplos arquivos ZIP e TAR, extrair com proteção contra Zip Slip,
organizar em subpastas individuais e acompanhar o status em tabela (DataTableView).
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.archive.multi_extract.logic import extract_batch_archives
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class MultiExtractTool(Tool):
    id = "archive.multi_extract"
    name = "Extrator em Lote de Arquivos"
    category = "Compactação"
    description = (
        "Descompacta múltiplos pacotes ZIP, TAR, TAR.GZ e TAR.BZ2 de forma simultânea, "
        "com organização em subpastas automáticas e proteção estrita contra ataques Zip Slip."
    )
    keywords = ["zip", "tar", "extrair", "lote", "descompactar", "multi", "arquivos", "seguranca"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return MultiExtractView(self, parent)


class MultiExtractView(QWidget):
    def __init__(self, tool: MultiExtractTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._selected_archives: List[Path] = []
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

        # Barra de Seleção de Destino
        dest_box = QHBoxLayout()
        dest_box.addWidget(QLabel("Pasta de Destino:"))
        self._txt_output_dir = QLineEdit()
        self._txt_output_dir.setPlaceholderText("Selecione a pasta onde os arquivos serão extraídos...")
        dest_box.addWidget(self._txt_output_dir)

        btn_browse_dest = QPushButton("Selecionar Destino...")
        btn_browse_dest.clicked.connect(self._on_browse_dest)
        dest_box.addWidget(btn_browse_dest)
        root_layout.addLayout(dest_box)

        # Controles e Opções
        ctrl_bar = QHBoxLayout()
        btn_add_files = QPushButton("Adicionar Arquivos Compactados...")
        btn_add_files.clicked.connect(self._on_add_archives)
        ctrl_bar.addWidget(btn_add_files)

        self._chk_subfolder = QCheckBox("Criar subpasta para cada pacote (ex: arquivo.zip -> ./arquivo/)")
        self._chk_subfolder.setChecked(True)
        ctrl_bar.addWidget(self._chk_subfolder)

        ctrl_bar.addStretch()

        self._btn_extract = QPushButton("Iniciar Extração em Lote")
        self._btn_extract.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self._btn_extract.clicked.connect(self._run_extraction)
        ctrl_bar.addWidget(self._btn_extract)

        root_layout.addLayout(ctrl_bar)

        self._lbl_status = QLabel("Nenhum arquivo compactado selecionado.")
        self._lbl_status.setStyleSheet("color: #4b5563; font-size: 11px; font-weight: bold;")
        root_layout.addWidget(self._lbl_status)

        # Tabela de Resultados com DataTableView
        cols = [
            Column("status", "Status", width=90),
            Column("archive_name", "Pacote Compactado", width=180),
            Column("files_count", "Arquivos Extraídos", width=130, align="right"),
            Column("dest_dir", "Pasta de Destino", width=260),
            Column("error", "Diagnóstico / Erro", width=220),
        ]
        self._table = DataTableView(cols, key="archive_path", parent=self)
        root_layout.addWidget(self._table)

    def _on_browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório de Destino")
        if folder:
            self._txt_output_dir.setText(folder)

    def _on_add_archives(self):
        fpaths, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Arquivos Compactados",
            "",
            "Arquivos Compactados (*.zip *.tar *.gz *.bz2 *.xz *.tgz);;Todos (*.*)",
        )
        if not fpaths:
            return

        for p in fpaths:
            path_obj = Path(p)
            if path_obj not in self._selected_archives:
                self._selected_archives.append(path_obj)

        self._lbl_status.setText(f"{len(self._selected_archives)} pacote(s) compactado(s) selecionado(s).")
        # Mostra registros pendentes na tabela
        records = [
            {
                "status": "PENDENTE",
                "archive_name": p.name,
                "archive_path": str(p),
                "files_count": "-",
                "dest_dir": "-",
                "error": "-",
            }
            for p in self._selected_archives
        ]
        self._table.set_records(records)

    def _run_extraction(self):
        if not self._selected_archives:
            QMessageBox.warning(self, "Aviso", "Por favor, adicione ao menos um arquivo compactado.")
            return

        dest_str = self._txt_output_dir.text().strip()
        if not dest_str:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma pasta de destino.")
            return

        dest_dir = Path(dest_str)
        create_sub = self._chk_subfolder.isChecked()

        self._lbl_status.setText("Extraindo pacotes em segundo plano...")
        self._btn_extract.setEnabled(False)

        self._runner.run(
            extract_batch_archives,
            self._selected_archives,
            dest_dir,
            create_subfolder=create_sub,
            on_success=self._on_extract_success,
            on_error=self._on_extract_error,
        )

    def _on_extract_success(self, results: list):
        self._btn_extract.setEnabled(True)
        self._table.set_records(results)

        ok_count = sum(1 for r in results if r.get("status") == "OK")
        fail_count = len(results) - ok_count

        if fail_count > 0:
            self._lbl_status.setStyleSheet("color: #b91c1c; font-weight: bold;")
        else:
            self._lbl_status.setStyleSheet("color: #047857; font-weight: bold;")

        self._lbl_status.setText(
            f"Extração concluída: {ok_count} com sucesso, {fail_count} falha(s)."
        )

    def _on_extract_error(self, exc: Exception):
        self._btn_extract.setEnabled(True)
        QMessageBox.critical(self, "Erro na Extração", f"Falha no processo: {exc}")
        self._lbl_status.setText("Erro na extração.")
