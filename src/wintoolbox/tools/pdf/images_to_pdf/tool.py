"""
Ferramenta: Conversor de Imagens para PDF.
Permite juntar múltiplas fotos e ilustrações em um PDF formatado com controle de folha e margens.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.pdf.images_to_pdf.logic import (
    PAGE_SIZES, convert_images_to_pdf
)


@register
class ImagesToPdfTool(Tool):
    id = "pdf.images_to_pdf"
    name = "Imagens para PDF"
    category = "PDF"
    description = "Conversor de imagens para PDF: transforma fotos e imagens (JPG, PNG, WebP) em documento PDF unificado com opções de orientação, margens e tamanho de folha."
    keywords = ["pdf", "imagens", "fotos", "jpg", "png", "a4", "álbum", "converter", "scan"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Conversor de Imagens para PDF")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        lbl_desc = QLabel("Adicione fotos, digitalizações ou ilustrações e una-as em um documento PDF formatado:")
        main_layout.addWidget(lbl_desc)

        # Layout com Lista à esquerda e Botões de controle à direita
        list_container = QHBoxLayout()
        self.list_images = QListWidget()
        self.list_images.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_images.setDragDropMode(QAbstractItemView.InternalMove)
        list_container.addWidget(self.list_images, stretch=1)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        btn_add = QPushButton("Adicionar Imagens...")
        btn_add.clicked.connect(self._on_add_images)
        btn_box.addWidget(btn_add)

        btn_up = QPushButton("Mover para Cima")
        btn_up.clicked.connect(self._on_move_up)
        btn_box.addWidget(btn_up)

        btn_down = QPushButton("Mover para Baixo")
        btn_down.clicked.connect(self._on_move_down)
        btn_box.addWidget(btn_down)

        btn_remove = QPushButton("Remover Seleção")
        btn_remove.clicked.connect(self._on_remove_selected)
        btn_box.addWidget(btn_remove)

        btn_clear = QPushButton("Limpar Lista")
        btn_clear.clicked.connect(self.list_images.clear)
        btn_box.addWidget(btn_clear)

        btn_box.addStretch()
        list_container.addLayout(btn_box)
        main_layout.addLayout(list_container)

        # Opções de Página
        grp_opts = QGroupBox("Formatação da Página")
        grid_opts = QGridLayout(grp_opts)
        grid_opts.setSpacing(10)

        grid_opts.addWidget(QLabel("Tamanho do papel:"), 0, 0)
        self.cmb_page_size = QComboBox()
        self.cmb_page_size.addItems(list(PAGE_SIZES.keys()))
        grid_opts.addWidget(self.cmb_page_size, 0, 1)

        grid_opts.addWidget(QLabel("Orientação:"), 0, 2)
        self.cmb_orientation = QComboBox()
        self.cmb_orientation.addItem("Automática (segue proporção da foto)", "auto")
        self.cmb_orientation.addItem("Retrato (Vertical)", "portrait")
        self.cmb_orientation.addItem("Paisagem (Horizontal)", "landscape")
        grid_opts.addWidget(self.cmb_orientation, 0, 3)

        grid_opts.addWidget(QLabel("Margem interna (pontos):"), 1, 0)
        self.spin_margin = QSpinBox()
        self.spin_margin.setRange(0, 100)
        self.spin_margin.setValue(20)
        grid_opts.addWidget(self.spin_margin, 1, 1)

        main_layout.addWidget(grp_opts)

        # Destino
        grp_out = QGroupBox("Arquivo de Destino")
        grid_out = QGridLayout(grp_out)

        grid_out.addWidget(QLabel("Salvar como:"), 0, 0)
        self.txt_output_pdf = QLineEdit()
        self.txt_output_pdf.setPlaceholderText("Selecione o caminho do PDF resultante...")
        grid_out.addWidget(self.txt_output_pdf, 0, 1)

        btn_browse_out = QPushButton("Procurar...")
        btn_browse_out.clicked.connect(self._on_browse_output)
        grid_out.addWidget(btn_browse_out, 0, 2)

        main_layout.addWidget(grp_out)

        # Barra de Ação
        actions = QHBoxLayout()
        self.lbl_status = QLabel("")
        actions.addWidget(self.lbl_status)
        actions.addStretch()

        self.btn_run = QPushButton("Gerar Documento PDF")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.clicked.connect(self._on_run)
        actions.addWidget(self.btn_run)

        main_layout.addLayout(actions)
        return container

    def _on_add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            None,
            "Selecionar Imagens",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tiff);;Todos os Arquivos (*.*)"
        )
        for f in files:
            self.list_images.addItem(f)

    def _on_move_up(self):
        row = self.list_images.currentRow()
        if row > 0:
            item = self.list_images.takeItem(row)
            self.list_images.insertItem(row - 1, item)
            self.list_images.setCurrentRow(row - 1)

    def _on_move_down(self):
        row = self.list_images.currentRow()
        if row < self.list_images.count() - 1:
            item = self.list_images.takeItem(row)
            self.list_images.insertItem(row + 1, item)
            self.list_images.setCurrentRow(row + 1)

    def _on_remove_selected(self):
        for item in self.list_images.selectedItems():
            self.list_images.takeItem(self.list_images.row(item))

    def _on_browse_output(self):
        file, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Documento PDF",
            "Imagens_Compiladas.pdf",
            "Arquivos PDF (*.pdf)"
        )
        if file:
            self.txt_output_pdf.setText(file)

    def _on_run(self):
        count = self.list_images.count()
        if count == 0:
            QMessageBox.warning(None, "Aviso", "Adicione pelo menos uma imagem à lista.")
            return

        out_path = self.txt_output_pdf.text().strip()
        if not out_path:
            QMessageBox.warning(None, "Aviso", "Informe o caminho do arquivo PDF de destino.")
            return

        image_files = [Path(self.list_images.item(i).text()) for i in range(count)]
        page_sz = self.cmb_page_size.currentText()
        orient = self.cmb_orientation.currentData()
        margin = self.spin_margin.value()

        self.btn_run.setEnabled(False)
        self.lbl_status.setText("Compilando imagens em PDF...")

        def _work(ctx: TaskContext):
            ctx.progress(10, 100, f"Processando {count} imagens...")
            res = convert_images_to_pdf(
                image_files,
                Path(out_path),
                page_size_name=page_sz,
                orientation=orient,
                margin_pt=margin
            )
            ctx.progress(100, 100, "PDF criado com sucesso!")
            return res

        def _done(result, exc):
            self.btn_run.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao gerar PDF de imagens: {exc}")
            else:
                self.lbl_status.setText("PDF gerado com sucesso!")
                QMessageBox.information(
                    None,
                    "Sucesso",
                    f"PDF gerado com sucesso contendo {count} páginas!\nArquivo: {result}"
                )

        def _on_prog(cur: int, tot: int, msg: str):
            if msg:
                self.lbl_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)
