"""
Ferramenta: Gerador de Ícones e Favicons (.ico e Pacote Web).
Cria ícones multi-resolução para Windows e pacotes completos de favicon para websites e PWA.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.favicon.logic import (
    DEFAULT_ICO_SIZES, generate_multi_size_ico, generate_web_favicon_package
)

@register
class ImageFaviconTool(Tool):
    id = "images.favicon"
    name = "Gerador de Ícones e Favicons"
    category = "Imagens"
    description = "Gere arquivos .ico multi-resolução para Windows ou pacote completo de favicons e manifest para web"
    keywords = ["favicon", "ico", "icone", "windows", "web", "manifest", "pwa", "apple touch", "site"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ImageFaviconView(self, parent)

class ImageFaviconView(QWidget):
    def __init__(self, tool: ImageFaviconTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Seleção de Imagem de Entrada
        card_in = QFrame()
        card_in.setProperty("class", "card")
        l_in = QVBoxLayout(card_in)
        l_in.setSpacing(10)

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Imagem base (PNG recomendado):"))
        self.txt_src = QLineEdit()
        self.txt_src.setPlaceholderText("Selecione um logo ou ícone em alta resolução (ex: 512x512 ou 1024x1024)...")
        row_sel.addWidget(self.txt_src, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_src)
        row_sel.addWidget(btn_browse)
        l_in.addLayout(row_sel)
        layout.addWidget(card_in)

        # Abas de Exportação
        tabs = QTabWidget()
        tabs.addTab(self._build_ico_tab(), "Arquivo .ICO (Windows)")
        tabs.addTab(self._build_web_tab(), "Pacote Completo Web Favicon")
        layout.addWidget(tabs)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_src(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem de Origem",
            "",
            "Imagens (*.png *.webp *.jpg *.jpeg *.bmp *.svg)"
        )
        if f:
            self.txt_src.setText(f)

    def _build_ico_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Tamanhos embutidos no arquivo .ico:"))
        grid_sizes = QGridLayout()
        self.chk_sizes = {}
        for idx, sz in enumerate(DEFAULT_ICO_SIZES):
            chk = QCheckBox(f"{sz} x {sz} px")
            chk.setChecked(True)
            self.chk_sizes[sz] = chk
            grid_sizes.addWidget(chk, idx // 4, idx % 4)
        layout.addLayout(grid_sizes)

        row_out = QHBoxLayout()
        btn_generate = QPushButton("Gerar Arquivo .ICO...")
        btn_generate.setProperty("class", "primary")
        btn_generate.setFixedHeight(36)
        btn_generate.clicked.connect(self._generate_ico)
        row_out.addWidget(btn_generate)
        row_out.addStretch()
        layout.addLayout(row_out)

        return w

    def _generate_ico(self):
        src_str = self.txt_src.text().strip()
        if not src_str or not Path(src_str).exists():
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma imagem de origem válida primeiro.")
            return

        selected_sizes = [sz for sz, chk in self.chk_sizes.items() if chk.isChecked()]
        if not selected_sizes:
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos um tamanho para o arquivo .ico.")
            return

        dst_str, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Arquivo de Ícone",
            str(Path(src_str).with_suffix(".ico")),
            "Ícones do Windows (*.ico)"
        )
        if not dst_str:
            return

        src_path = Path(src_str)
        dst_path = Path(dst_str)

        try:
            generate_multi_size_ico(src_path, dst_path, selected_sizes)
            QMessageBox.information(
                self,
                "Ícone Gerado",
                f"Arquivo de ícone gravado com sucesso em:\n{dst_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao gerar ícone: {str(e)}")

    def _build_web_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        card_pwa = QFrame()
        card_pwa.setProperty("class", "card")
        l_pwa = QGridLayout(card_pwa)
        l_pwa.setHorizontalSpacing(16)
        l_pwa.setVerticalSpacing(8)

        l_pwa.addWidget(QLabel("Nome do Web App / Site:"), 0, 0)
        self.txt_app_name = QLineEdit("Meu Aplicativo Web")
        l_pwa.addWidget(self.txt_app_name, 0, 1)

        l_pwa.addWidget(QLabel("Cor de tema (Hex):"), 1, 0)
        self.txt_theme_color = QLineEdit("#0078D4")
        l_pwa.addWidget(self.txt_theme_color, 1, 1)

        layout.addWidget(card_pwa)

        btn_generate_pack = QPushButton("Gerar Pacote Completo em Pasta...")
        btn_generate_pack.setProperty("class", "primary")
        btn_generate_pack.setFixedHeight(36)
        btn_generate_pack.clicked.connect(self._generate_web_pack)
        layout.addWidget(btn_generate_pack)

        layout.addWidget(QLabel("Código HTML para inserir na tag <head> do seu site:"))
        self.txt_snippet = QPlainTextEdit()
        self.txt_snippet.setPlaceholderText("O snippet HTML será exibido aqui após a geração do pacote...")
        self.txt_snippet.setReadOnly(True)
        self.txt_snippet.setFixedHeight(120)
        layout.addWidget(self.txt_snippet)

        btn_copy_html = QPushButton("Copiar Snippet HTML")
        btn_copy_html.clicked.connect(self._copy_html)
        layout.addWidget(btn_copy_html)

        return w

    def _generate_web_pack(self):
        src_str = self.txt_src.text().strip()
        if not src_str or not Path(src_str).exists():
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma imagem de origem válida primeiro.")
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Salvar o Pacote de Favicons")
        if not out_dir:
            return

        try:
            res = generate_web_favicon_package(
                src=Path(src_str),
                out_dir=Path(out_dir),
                app_name=self.txt_app_name.text().strip(),
                theme_color=self.txt_theme_color.text().strip()
            )
            self.txt_snippet.setPlainText(res["html_snippet"])
            QMessageBox.information(
                self,
                "Pacote Gerado com Sucesso",
                f"Todos os arquivos de favicon, manifest e ícones foram gerados em:\n{out_dir}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao gerar pacote: {str(e)}")

    def _copy_html(self):
        txt = self.txt_snippet.toPlainText().strip()
        if txt:
            QApplication.clipboard().setText(txt)
            QMessageBox.information(self, "Copiado", "Snippet HTML copiado para a área de transferência!")
