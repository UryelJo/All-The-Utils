"""
Interface gráfica da ferramenta Editor e Sanitizador de Metadados PDF (pdf.metadata_editor).
Permite inspecionar e alterar Título, Autor, Assunto, Software Criador e Produtor,
além de limpar e anonimizar todos os metadados de PDFs em lote para privacidade.
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.metadata_editor.logic import (
    batch_sanitize_metadata,
    read_pdf_metadata,
    update_pdf_metadata,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class PdfMetadataEditorTool(Tool):
    id = "pdf.metadata_editor"
    name = "Editor e Sanitizador de Metadados PDF"
    category = "PDF"
    description = (
        "Edite ou remova metadados (Título, Autor, Criador, Palavras-chave) de arquivos PDF. "
        "Permite higienização em lote para proteção de privacidade e anonimização."
    )
    keywords = ["pdf", "metadados", "autor", "titulo", "anonimizar", "limpar", "privacidade", "propriedades"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PdfMetadataEditorView(self, parent)


class PdfMetadataEditorView(QWidget):
    def __init__(self, tool: PdfMetadataEditorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._current_pdf_path: Optional[Path] = None
        self._batch_files: List[Path] = []
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

        # Abas
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_single_tab(), "Editar Documento Individual")
        self._tabs.addTab(self._build_batch_tab(), "Higienizar em Lote (Privacidade)")
        root_layout.addWidget(self._tabs)

    def _build_single_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Seleção do PDF
        top_bar = QHBoxLayout()
        self._txt_single_path = QLineEdit()
        self._txt_single_path.setPlaceholderText("Selecione um arquivo PDF para carregar seus metadados...")
        self._txt_single_path.setReadOnly(True)
        top_bar.addWidget(self._txt_single_path)

        btn_browse = QPushButton("Abrir PDF...")
        btn_browse.clicked.connect(self._on_browse_single_pdf)
        top_bar.addWidget(btn_browse)
        layout.addLayout(top_bar)

        # Campos de Metadados
        form_group = QGroupBox("Propriedades e Metadados do Documento")
        form_layout = QVBoxLayout(form_group)

        self._fields = {}
        fields_info = [
            ("title", "Título:"),
            ("author", "Autor:"),
            ("subject", "Assunto:"),
            ("keywords", "Palavras-chave:"),
            ("creator", "Software Criador:"),
            ("producer", "Produtor PDF:"),
        ]

        for key, label_text in fields_info:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(130)
            row.addWidget(lbl)
            txt = QLineEdit()
            row.addWidget(txt)
            self._fields[key] = txt
            form_layout.addLayout(row)

        layout.addWidget(form_group)

        # Ações
        act_bar = QHBoxLayout()
        self._chk_clean = QCheckBox("Remover e higienizar todos os metadados (Privacidade Total)")
        act_bar.addWidget(self._chk_clean)
        act_bar.addStretch()

        btn_save = QPushButton("Salvar Novo PDF...")
        btn_save.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        btn_save.clicked.connect(self._on_save_single_pdf)
        act_bar.addWidget(btn_save)

        layout.addLayout(act_bar)
        self._lbl_single_status = QLabel("Nenhum arquivo aberto.")
        self._lbl_single_status.setStyleSheet("color: #4b5563; font-size: 11px;")
        layout.addWidget(self._lbl_single_status)

        layout.addStretch()
        return widget

    def _build_batch_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        ctrl_bar = QHBoxLayout()
        btn_add = QPushButton("Adicionar Arquivos PDF...")
        btn_add.clicked.connect(self._on_add_batch_files)
        ctrl_bar.addWidget(btn_add)

        self._btn_run_batch = QPushButton("Higienizar Metadados de Todos...")
        self._btn_run_batch.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self._btn_run_batch.clicked.connect(self._on_run_batch_sanitize)
        ctrl_bar.addWidget(self._btn_run_batch)

        ctrl_bar.addStretch()
        layout.addLayout(ctrl_bar)

        self._lbl_batch_status = QLabel("Nenhum PDF selecionado.")
        self._lbl_batch_status.setStyleSheet("color: #4b5563; font-size: 11px;")
        layout.addWidget(self._lbl_batch_status)

        # Tabela com DataTableView
        cols = [
            Column("status", "Status", width=90),
            Column("filename", "Nome do Arquivo", width=220),
            Column("output_path", "Destino Limpo", width=380),
        ]
        self._batch_table = DataTableView(cols, key="filename", parent=self)
        layout.addWidget(self._batch_table)

        return widget

    def _on_browse_single_pdf(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo PDF", "", "Documentos PDF (*.pdf)")
        if not fpath:
            return

        self._current_pdf_path = Path(fpath)
        self._txt_single_path.setText(str(self._current_pdf_path))

        try:
            meta = read_pdf_metadata(self._current_pdf_path)
            for k, field in self._fields.items():
                field.setText(meta.get(k, ""))
            self._lbl_single_status.setText(
                f"PDF carregado ({meta.get('total_pages', 0)} página(s)). Modificado em: {meta.get('mod_date', '-')}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao Ler PDF", f"Falha ao ler metadados: {exc}")

    def _on_save_single_pdf(self):
        if not self._current_pdf_path or not self._current_pdf_path.is_file():
            QMessageBox.warning(self, "Aviso", "Por favor, abra um arquivo PDF primeiro.")
            return

        default_out = f"limpo_{self._current_pdf_path.name}"
        out_fpath, _ = QFileDialog.getSaveFileName(self, "Salvar PDF com Novos Metadados", default_out, "PDF (*.pdf)")
        if not out_fpath:
            return

        clean_all = self._chk_clean.isChecked()
        new_meta = {k: field.text().strip() for k, field in self._fields.items()}

        try:
            res = update_pdf_metadata(self._current_pdf_path, Path(out_fpath), new_metadata=new_meta, clean_all=clean_all)
            msg = "PDF higienizado com sucesso!" if clean_all else "Metadados atualizados com sucesso!"
            QMessageBox.information(self, "Sucesso", f"{msg}\nSalvo em:\n{res['output_path']}")
            self._lbl_single_status.setText("Arquivo salvo com sucesso!")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao Salvar", f"Falha na gravação do PDF: {exc}")

    def _on_add_batch_files(self):
        fpaths, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos PDF", "", "Documentos PDF (*.pdf)")
        if not fpaths:
            return
        for p in fpaths:
            p_obj = Path(p)
            if p_obj not in self._batch_files:
                self._batch_files.append(p_obj)

        self._lbl_batch_status.setText(f"{len(self._batch_files)} arquivo(s) selecionado(s).")
        records = [{"status": "PENDENTE", "filename": p.name, "output_path": "-"} for p in self._batch_files]
        self._batch_table.set_records(records)

    def _on_run_batch_sanitize(self):
        if not self._batch_files:
            QMessageBox.warning(self, "Aviso", "Por favor, adicione ao menos um arquivo PDF.")
            return

        out_folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino dos PDFs Higienizados")
        if not out_folder:
            return

        self._lbl_batch_status.setText("Higienizando metadados em lote...")
        self._btn_run_batch.setEnabled(False)

        self._runner.run(
            batch_sanitize_metadata,
            self._batch_files,
            Path(out_folder),
            on_success=self._on_batch_success,
            on_error=self._on_batch_error,
        )

    def _on_batch_success(self, results: list):
        self._btn_run_batch.setEnabled(True)
        self._batch_table.set_records(results)
        self._lbl_batch_status.setText(f"{len(results)} arquivo(s) processados com sucesso!")
        QMessageBox.information(self, "Sucesso", "Higienização de metadados em lote concluída!")

    def _on_batch_error(self, exc: Exception):
        self._btn_run_batch.setEnabled(True)
        QMessageBox.critical(self, "Erro", f"Falha no processamento: {exc}")
        self._lbl_batch_status.setText("Erro na higienização.")
