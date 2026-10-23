"""
Ferramenta: Extrator de Texto e Imagens de PDF.
Permite extrair conteúdo estruturado de documentos PDF sem perdas.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout,
    QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.pdf.extract.logic import (
    extract_images_from_pdf, extract_text_from_pdf
)


@register
class PdfExtractTool(Tool):
    id = "pdf.extract"
    name = "Extrator de Texto e Imagens de PDF"
    category = "PDF"
    description = "Extraia texto integral página a página ou extraia todas as fotos e ilustrações embutidas em PDFs"
    keywords = ["pdf", "extrair", "texto", "imagens", "descompactar", "ocr", "figuras", "fotos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Extrator de Texto e Imagens de PDF")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._build_text_tab(), "Extrair Texto")
        tabs.addTab(self._build_images_tab(), "Extrair Imagens")
        main_layout.addWidget(tabs)

        return container

    # -------------------------------------------------------------------------
    # Aba 1: Extrair Texto
    # -------------------------------------------------------------------------
    def _build_text_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seletor de Arquivo
        grp_src = QGroupBox("Documento PDF de Entrada")
        grid_src = QGridLayout(grp_src)
        grid_src.addWidget(QLabel("Arquivo PDF:"), 0, 0)
        self.txt_text_src = QLineEdit()
        self.txt_text_src.setPlaceholderText("Selecione o arquivo PDF...")
        grid_src.addWidget(self.txt_text_src, 0, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_text_src)
        grid_src.addWidget(btn_browse, 0, 2)

        self.chk_headers = QCheckBox("Incluir cabeçalhos de identificação de página (ex: '--- Página 1 ---')")
        self.chk_headers.setChecked(True)
        grid_src.addWidget(self.chk_headers, 1, 0, 1, 3)
        layout.addWidget(grp_src)

        # Ações
        act_box = QHBoxLayout()
        self.btn_run_text = QPushButton("Extrair Texto Agora")
        self.btn_run_text.setProperty("class", "primary")
        self.btn_run_text.clicked.connect(self._on_run_extract_text)
        act_box.addWidget(self.btn_run_text)

        self.lbl_text_status = QLabel("")
        act_box.addWidget(self.lbl_text_status)
        act_box.addStretch()

        btn_copy = QPushButton("Copiar Texto")
        btn_copy.clicked.connect(self._on_copy_text)
        act_box.addWidget(btn_copy)

        btn_save = QPushButton("Salvar como .txt...")
        btn_save.clicked.connect(self._on_save_text)
        act_box.addWidget(btn_save)

        layout.addLayout(act_box)

        # Visualizador de Texto
        self.txt_display = QTextEdit()
        self.txt_display.setPlaceholderText("O texto extraído aparecerá aqui...")
        self.txt_display.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.txt_display, stretch=1)

        return tab

    def _on_browse_text_src(self):
        file, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if file:
            self.txt_text_src.setText(file)

    def _on_run_extract_text(self):
        src = self.txt_text_src.text().strip()
        if not src or not Path(src).is_file():
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo PDF válido.")
            return

        headers = self.chk_headers.isChecked()
        self.btn_run_text.setEnabled(False)
        self.lbl_text_status.setText("Extraindo texto...")

        def _work(ctx: TaskContext):
            ctx.progress(10, 100, "Lendo páginas do PDF...")
            txt = extract_text_from_pdf(Path(src), include_page_headers=headers)
            ctx.progress(100, 100, "Extração concluída!")
            return txt

        def _done(result, exc):
            self.btn_run_text.setEnabled(True)
            if exc:
                self.lbl_text_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha na extração de texto: {exc}")
            else:
                self.txt_display.setPlainText(result)
                chars = len(result)
                self.lbl_text_status.setText(f"Texto extraído ({chars:,} caracteres).")

        run_task(_work, on_done=_done)

    def _on_copy_text(self):
        content = self.txt_display.toPlainText()
        if content:
            QApplication.clipboard().setText(content)
            QMessageBox.information(None, "Copiado", "Texto copiado para a área de transferência!")

    def _on_save_text(self):
        content = self.txt_display.toPlainText()
        if not content:
            QMessageBox.warning(None, "Aviso", "Nenhum texto para salvar.")
            return
        file, _ = QFileDialog.getSaveFileName(None, "Salvar Texto Extraído", "texto_extraido.txt", "Texto (*.txt)")
        if file:
            Path(file).write_text(content, encoding="utf-8")
            QMessageBox.information(None, "Salvo", f"Arquivo salvo com sucesso em:\n{file}")

    # -------------------------------------------------------------------------
    # Aba 2: Extrair Imagens
    # -------------------------------------------------------------------------
    def _build_images_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grp_box = QGroupBox("Configurações de Extração de Imagens")
        grid = QGridLayout(grp_box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("PDF de entrada:"), 0, 0)
        self.txt_img_src = QLineEdit()
        self.txt_img_src.setPlaceholderText("Selecione o arquivo PDF...")
        grid.addWidget(self.txt_img_src, 0, 1)

        btn_browse_pdf = QPushButton("Procurar...")
        btn_browse_pdf.clicked.connect(self._on_browse_img_src)
        grid.addWidget(btn_browse_pdf, 0, 2)

        grid.addWidget(QLabel("Pasta de destino:"), 1, 0)
        self.txt_img_out_dir = QLineEdit()
        grid.addWidget(self.txt_img_out_dir, 1, 1)

        btn_browse_dir = QPushButton("Procurar...")
        btn_browse_dir.clicked.connect(self._on_browse_img_dir)
        grid.addWidget(btn_browse_dir, 1, 2)

        grid.addWidget(QLabel("Dimensão mínima (largura/altura em px):"), 2, 0)
        self.spin_min_dim = QSpinBox()
        self.spin_min_dim.setRange(5, 5000)
        self.spin_min_dim.setValue(40)
        self.spin_min_dim.setToolTip("Ignora ícones e elementos gráficos minúsculos menores que este tamanho")
        grid.addWidget(self.spin_min_dim, 2, 1)

        layout.addWidget(grp_box)

        # Barra de Ação
        act_box = QHBoxLayout()
        self.btn_run_images = QPushButton("Extrair Imagens Agora")
        self.btn_run_images.setProperty("class", "primary")
        self.btn_run_images.clicked.connect(self._on_run_extract_images)
        act_box.addWidget(self.btn_run_images)

        self.lbl_img_status = QLabel("")
        act_box.addWidget(self.lbl_img_status)
        act_box.addStretch()

        layout.addLayout(act_box)
        layout.addStretch()

        return tab

    def _on_browse_img_src(self):
        file, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if file:
            p = Path(file)
            self.txt_img_src.setText(str(p))
            if not self.txt_img_out_dir.text():
                self.txt_img_out_dir.setText(str(p.parent / f"{p.stem}_imagens"))

    def _on_browse_img_dir(self):
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Destino")
        if folder:
            self.txt_img_out_dir.setText(folder)

    def _on_run_extract_images(self):
        src = self.txt_img_src.text().strip()
        if not src or not Path(src).is_file():
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo PDF válido.")
            return

        out_dir = self.txt_img_out_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(None, "Aviso", "Informe a pasta de saída.")
            return

        min_dim = self.spin_min_dim.value()
        self.btn_run_images.setEnabled(False)
        self.lbl_img_status.setText("Extraindo imagens embutidas...")

        def _work(ctx: TaskContext):
            ctx.progress(10, 100, "Varrendo imagens no PDF...")
            files = extract_images_from_pdf(Path(src), Path(out_dir), min_dimension=min_dim)
            ctx.progress(100, 100, "Extração de imagens concluída!")
            return files

        def _done(result, exc):
            self.btn_run_images.setEnabled(True)
            if exc:
                self.lbl_img_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao extrair imagens: {exc}")
            else:
                count = len(result)
                self.lbl_img_status.setText(f"{count} imagens extraídas.")
                QMessageBox.information(
                    None,
                    "Sucesso",
                    f"{count} imagens foram extraídas com sucesso para:\n{out_dir}"
                )

        run_task(_work, on_done=_done)
