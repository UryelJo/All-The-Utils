"""
Ferramenta: Divisor e Juntador de Arquivos PDF.
Interface moderna em abas com suporte a reordenação, intervalos e execução em segundo plano.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.pdf.split_merge.logic import (
    get_pdf_info, merge_pdfs, split_pdf
)


@register
class PdfSplitMergeTool(Tool):
    id = "pdf.split_merge"
    name = "Divisor e Juntador de PDF"
    category = "PDF"
    description = "Juntador e divisor de PDFs: combina múltiplos documentos em um único PDF na ordem desejada ou extrai intervalos e páginas específicas."
    keywords = ["pdf", "juntar", "dividir", "split", "merge", "páginas", "unir", "separar", "intervalos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Divisor e Juntador de PDF")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._build_merge_tab(), "Juntar PDFs (Merge)")
        tabs.addTab(self._build_split_tab(), "Dividir PDF (Split)")
        main_layout.addWidget(tabs)

        return container

    # -------------------------------------------------------------------------
    # Aba 1: Juntar PDFs (Merge)
    # -------------------------------------------------------------------------
    def _build_merge_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_info = QLabel("Selecione os arquivos PDF que deseja unificar e ajuste a ordem desejada:")
        layout.addWidget(lbl_info)

        content_layout = QHBoxLayout()

        self.list_merge_files = QListWidget()
        self.list_merge_files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_merge_files.setDragDropMode(QAbstractItemView.InternalMove)
        content_layout.addWidget(self.list_merge_files, stretch=1)

        # Botões de controle da lista
        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        btn_add = QPushButton("Adicionar PDFs...")
        btn_add.clicked.connect(self._on_add_merge_files)
        btn_box.addWidget(btn_add)

        btn_up = QPushButton("Mover para Cima")
        btn_up.clicked.connect(self._on_move_up)
        btn_box.addWidget(btn_up)

        btn_down = QPushButton("Mover para Baixo")
        btn_down.clicked.connect(self._on_move_down)
        btn_box.addWidget(btn_down)

        btn_remove = QPushButton("Remover Seleção")
        btn_remove.clicked.connect(self._on_remove_merge_file)
        btn_box.addWidget(btn_remove)

        btn_clear = QPushButton("Limpar Tudo")
        btn_clear.clicked.connect(self.list_merge_files.clear)
        btn_box.addWidget(btn_clear)

        btn_box.addStretch()
        content_layout.addLayout(btn_box)
        layout.addLayout(content_layout)

        # Opções de saída
        opts_box = QGroupBox("Configurações de Saída")
        opts_layout = QGridLayout(opts_box)
        opts_layout.setContentsMargins(10, 10, 10, 10)
        opts_layout.setSpacing(8)

        self.chk_bookmarks = QCheckBox("Adicionar marcadores de índice com os nomes dos arquivos")
        self.chk_bookmarks.setChecked(True)
        opts_layout.addWidget(self.chk_bookmarks, 0, 0, 1, 3)

        opts_layout.addWidget(QLabel("Destino do PDF unificado:"), 1, 0)
        self.txt_merge_output = QLineEdit()
        self.txt_merge_output.setPlaceholderText("Selecione o arquivo de destino (ex: C:/Documentos/Unificado.pdf)")
        opts_layout.addWidget(self.txt_merge_output, 1, 1)

        btn_browse_out = QPushButton("Procurar...")
        btn_browse_out.clicked.connect(self._on_browse_merge_output)
        opts_layout.addWidget(btn_browse_out, 1, 2)

        layout.addWidget(opts_box)

        # Ações
        actions_layout = QHBoxLayout()
        self.lbl_merge_status = QLabel("")
        actions_layout.addWidget(self.lbl_merge_status)
        actions_layout.addStretch()

        self.btn_run_merge = QPushButton("Juntar PDFs Agora")
        self.btn_run_merge.setProperty("class", "primary")
        self.btn_run_merge.clicked.connect(self._on_run_merge)
        actions_layout.addWidget(self.btn_run_merge)

        layout.addLayout(actions_layout)
        return tab

    def _on_add_merge_files(self):
        files, _ = QFileDialog.getOpenFileNames(None, "Selecionar Arquivos PDF", "", "Arquivos PDF (*.pdf)")
        for f in files:
            self.list_merge_files.addItem(f)

    def _on_move_up(self):
        row = self.list_merge_files.currentRow()
        if row > 0:
            item = self.list_merge_files.takeItem(row)
            self.list_merge_files.insertItem(row - 1, item)
            self.list_merge_files.setCurrentRow(row - 1)

    def _on_move_down(self):
        row = self.list_merge_files.currentRow()
        if row < self.list_merge_files.count() - 1:
            item = self.list_merge_files.takeItem(row)
            self.list_merge_files.insertItem(row + 1, item)
            self.list_merge_files.setCurrentRow(row + 1)

    def _on_remove_merge_file(self):
        for item in self.list_merge_files.selectedItems():
            self.list_merge_files.takeItem(self.list_merge_files.row(item))

    def _on_browse_merge_output(self):
        file, _ = QFileDialog.getSaveFileName(None, "Salvar PDF Unificado", "PDF_Unificado.pdf", "Arquivos PDF (*.pdf)")
        if file:
            self.txt_merge_output.setText(file)

    def _on_run_merge(self):
        count = self.list_merge_files.count()
        if count < 2:
            QMessageBox.warning(None, "Aviso", "Adicione pelo menos 2 arquivos PDF para unificar.")
            return

        out_path = self.txt_merge_output.text().strip()
        if not out_path:
            QMessageBox.warning(None, "Aviso", "Informe o arquivo PDF de destino.")
            return

        pdf_files = [Path(self.list_merge_files.item(i).text()) for i in range(count)]
        add_bm = self.chk_bookmarks.isChecked()

        self.btn_run_merge.setEnabled(False)
        self.lbl_merge_status.setText("Unificando arquivos...")

        def _work(ctx: TaskContext):
            ctx.progress(10, 100, "Unindo documentos PDF...")
            res = merge_pdfs(pdf_files, Path(out_path), add_bookmarks=add_bm)
            ctx.progress(100, 100, "PDF gerado com sucesso!")
            return res

        def _done(result, exc):
            self.btn_run_merge.setEnabled(True)
            if exc:
                self.lbl_merge_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao unir PDFs: {exc}")
            else:
                self.lbl_merge_status.setText("Concluído com sucesso!")
                QMessageBox.information(None, "Sucesso", f"PDF unificado gerado em:\n{result}")

        run_task(_work, on_done=_done)

    # -------------------------------------------------------------------------
    # Aba 2: Dividir PDF (Split)
    # -------------------------------------------------------------------------
    def _build_split_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção do PDF
        grp_src = QGroupBox("Arquivo PDF de Origem")
        grid_src = QGridLayout(grp_src)
        grid_src.addWidget(QLabel("PDF de entrada:"), 0, 0)
        self.txt_split_src = QLineEdit()
        self.txt_split_src.setPlaceholderText("Selecione um arquivo PDF para dividir")
        grid_src.addWidget(self.txt_split_src, 0, 1)

        btn_browse_src = QPushButton("Procurar...")
        btn_browse_src.clicked.connect(self._on_browse_split_src)
        grid_src.addWidget(btn_browse_src, 0, 2)

        self.lbl_pdf_info = QLabel("Total de páginas: - | Tamanho: -")
        self.lbl_pdf_info.setStyleSheet("color: gray; font-size: 11px;")
        grid_src.addWidget(self.lbl_pdf_info, 1, 1, 1, 2)
        layout.addWidget(grp_src)

        # Modos de Divisão
        grp_mode = QGroupBox("Modo de Divisão")
        grid_mode = QGridLayout(grp_mode)

        grid_mode.addWidget(QLabel("Estratégia:"), 0, 0)
        self.cmb_split_mode = QComboBox()
        self.cmb_split_mode.addItem("Uma página por arquivo (todas individuais)", "all")
        self.cmb_split_mode.addItem("Intervalos customizados (ex: 1-3, 5, 8-10)", "range")
        self.cmb_split_mode.addItem("Agrupar a cada N páginas", "each_n")
        self.cmb_split_mode.currentIndexChanged.connect(self._on_split_mode_changed)
        grid_mode.addWidget(self.cmb_split_mode, 0, 1)

        self.lbl_range = QLabel("Intervalos:")
        self.lbl_range.setVisible(False)
        grid_mode.addWidget(self.lbl_range, 1, 0)

        self.txt_range = QLineEdit()
        self.txt_range.setPlaceholderText("Ex: 1-5, 8, 11-15")
        self.txt_range.setVisible(False)
        grid_mode.addWidget(self.txt_range, 1, 1)

        self.lbl_each_n = QLabel("Quantidade por parte:")
        self.lbl_each_n.setVisible(False)
        grid_mode.addWidget(self.lbl_each_n, 2, 0)

        self.spin_each_n = QSpinBox()
        self.spin_each_n.setRange(1, 9999)
        self.spin_each_n.setValue(2)
        self.spin_each_n.setVisible(False)
        grid_mode.addWidget(self.spin_each_n, 2, 1)

        layout.addWidget(grp_mode)

        # Destino
        grp_dst = QGroupBox("Destino dos Arquivos")
        grid_dst = QGridLayout(grp_dst)

        grid_dst.addWidget(QLabel("Pasta de saída:"), 0, 0)
        self.txt_split_out_dir = QLineEdit()
        grid_dst.addWidget(self.txt_split_out_dir, 0, 1)

        btn_browse_dir = QPushButton("Procurar...")
        btn_browse_dir.clicked.connect(self._on_browse_split_dir)
        grid_dst.addWidget(btn_browse_dir, 0, 2)

        grid_dst.addWidget(QLabel("Prefixo do nome:"), 1, 0)
        self.txt_split_prefix = QLineEdit()
        self.txt_split_prefix.setPlaceholderText("(Padrão: nome original do arquivo)")
        grid_dst.addWidget(self.txt_split_prefix, 1, 1)

        layout.addWidget(grp_dst)

        # Ações
        actions_layout = QHBoxLayout()
        self.lbl_split_status = QLabel("")
        actions_layout.addWidget(self.lbl_split_status)
        actions_layout.addStretch()

        self.btn_run_split = QPushButton("Dividir PDF Agora")
        self.btn_run_split.setProperty("class", "primary")
        self.btn_run_split.clicked.connect(self._on_run_split)
        actions_layout.addWidget(self.btn_run_split)

        layout.addLayout(actions_layout)
        return tab

    def _on_browse_split_src(self):
        file, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if file:
            p = Path(file)
            self.txt_split_src.setText(str(p))
            if not self.txt_split_out_dir.text():
                self.txt_split_out_dir.setText(str(p.parent / f"{p.stem}_dividido"))
            try:
                info = get_pdf_info(p)
                sz_mb = info["size_bytes"] / (1024 * 1024)
                self.lbl_pdf_info.setText(f"Total de páginas: {info['pages']} | Tamanho: {sz_mb:.2f} MB")
            except Exception as e:
                self.lbl_pdf_info.setText(f"Aviso ao ler informações: {e}")

    def _on_browse_split_dir(self):
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Destino")
        if folder:
            self.txt_split_out_dir.setText(folder)

    def _on_split_mode_changed(self):
        mode = self.cmb_split_mode.currentData()
        self.lbl_range.setVisible(mode == "range")
        self.txt_range.setVisible(mode == "range")
        self.lbl_each_n.setVisible(mode == "each_n")
        self.spin_each_n.setVisible(mode == "each_n")

    def _on_run_split(self):
        src = self.txt_split_src.text().strip()
        if not src or not Path(src).is_file():
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo PDF válido para dividir.")
            return

        out_dir = self.txt_split_out_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(None, "Aviso", "Informe a pasta de saída.")
            return

        mode = self.cmb_split_mode.currentData()
        r_str = self.txt_range.text().strip()
        each_n_val = self.spin_each_n.value()
        pfx = self.txt_split_prefix.text().strip()

        self.btn_run_split.setEnabled(False)
        self.lbl_split_status.setText("Dividindo documento PDF...")

        def _work(ctx: TaskContext):
            ctx.progress(10, 100, "Processando páginas do PDF...")
            files = split_pdf(
                Path(src),
                Path(out_dir),
                split_mode=mode,
                range_str=r_str,
                each_n=each_n_val,
                prefix=pfx
            )
            ctx.progress(100, 100, "Divisão concluída com sucesso!")
            return files

        def _done(result, exc):
            self.btn_run_split.setEnabled(True)
            if exc:
                self.lbl_split_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao dividir PDF: {exc}")
            else:
                count = len(result)
                self.lbl_split_status.setText(f"{count} arquivos gerados.")
                QMessageBox.information(
                    None,
                    "Sucesso",
                    f"Divisão concluída com sucesso!\n{count} arquivos gerados em:\n{out_dir}"
                )

        run_task(_work, on_done=_done)
