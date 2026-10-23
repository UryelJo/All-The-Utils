"""
Ferramenta: Extrator de Paleta de Cores Dominantes de Imagens.
Analisa a imagem e extrai as cores predominantes com códigos HEX, RGB, HSL e exportação CSS/JSON.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.palette.logic import (
    export_palette_css, export_palette_image, export_palette_json,
    extract_dominant_colors
)

@register
class ImagePaletteTool(Tool):
    id = "images.palette"
    name = "Extrator de Paleta de Cores"
    category = "Imagens"
    description = "Extraia as cores dominantes de qualquer imagem com códigos HEX, RGB, HSL e exportação para CSS e JSON"
    keywords = ["paleta", "cores", "extrator", "dominante", "hex", "rgb", "hsl", "css", "designer", "fotos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ImagePaletteView(self, parent)

class ImagePaletteView(QWidget):
    def __init__(self, tool: ImagePaletteTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.extracted_colors = []
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

        # Seletor de Imagem e Configurações
        card_ctrl = QFrame()
        card_ctrl.setProperty("class", "card")
        l_ctrl = QVBoxLayout(card_ctrl)
        l_ctrl.setSpacing(10)

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Imagem para analisar:"))
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Selecione uma imagem...")
        row_sel.addWidget(self.txt_path, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_image)
        row_sel.addWidget(btn_browse)
        l_ctrl.addLayout(row_sel)

        row_opts = QHBoxLayout()
        self.lbl_num_colors = QLabel("Cores a extrair (6):")
        row_opts.addWidget(self.lbl_num_colors)

        self.slider_num = QSlider(Qt.Horizontal)
        self.slider_num.setRange(3, 12)
        self.slider_num.setValue(6)
        self.slider_num.setFixedWidth(160)
        self.slider_num.valueChanged.connect(
            lambda v: self.lbl_num_colors.setText(f"Cores a extrair ({v}):")
        )
        row_opts.addWidget(self.slider_num)
        row_opts.addSpacing(20)

        btn_extract = QPushButton("Extrair Paleta de Cores")
        btn_extract.setProperty("class", "primary")
        btn_extract.clicked.connect(self._extract_palette)
        row_opts.addWidget(btn_extract)
        row_opts.addStretch()
        l_ctrl.addLayout(row_opts)

        layout.addWidget(card_ctrl)

        # Área de Exibição dos Cards de Cores
        layout.addWidget(QLabel("Cores Dominantes Identificadas:"))
        self.grid_colors = QGridLayout()
        self.grid_colors.setSpacing(12)
        layout.addLayout(self.grid_colors)

        # Barra de Ações de Exportação
        card_export = QFrame()
        card_export.setProperty("class", "card")
        l_exp = QHBoxLayout(card_export)
        l_exp.setSpacing(10)

        self.btn_copy_css = QPushButton("Copiar como Variáveis CSS")
        self.btn_copy_css.setEnabled(False)
        self.btn_copy_css.clicked.connect(self._copy_css)
        l_exp.addWidget(self.btn_copy_css)

        self.btn_copy_json = QPushButton("Copiar como JSON")
        self.btn_copy_json.setEnabled(False)
        self.btn_copy_json.clicked.connect(self._copy_json)
        l_exp.addWidget(self.btn_copy_json)

        self.btn_save_img = QPushButton("Salvar Imagem da Paleta (.png)...")
        self.btn_save_img.setEnabled(False)
        self.btn_save_img.clicked.connect(self._save_palette_image)
        l_exp.addWidget(self.btn_save_img)
        l_exp.addStretch()

        layout.addWidget(card_export)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para Paleta",
            "",
            "Imagens (*.png *.webp *.jpg *.jpeg *.bmp)"
        )
        if f:
            self.txt_path.setText(f)
            self._extract_palette()

    def _extract_palette(self):
        src_str = self.txt_path.text().strip()
        if not src_str or not Path(src_str).exists():
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma imagem válida primeiro.")
            return

        p = Path(src_str)
        num_c = self.slider_num.value()

        try:
            self.extracted_colors = extract_dominant_colors(p, num_c)
            self._render_colors()
            has_colors = len(self.extracted_colors) > 0
            self.btn_copy_css.setEnabled(has_colors)
            self.btn_copy_json.setEnabled(has_colors)
            self.btn_save_img.setEnabled(has_colors)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao extrair paleta: {str(e)}")

    def _render_colors(self):
        # Limpa widgets anteriores
        while self.grid_colors.count():
            item = self.grid_colors.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, c in enumerate(self.extracted_colors):
            card = QFrame()
            card.setProperty("class", "card")
            card.setMinimumWidth(180)
            l = QVBoxLayout(card)
            l.setContentsMargins(8, 8, 8, 8)
            l.setSpacing(6)

            # Bloco retangular da cor
            color_box = QFrame()
            color_box.setFixedHeight(60)
            color_box.setStyleSheet(f"background-color: {c['hex']}; border-radius: 4px; border: 1px solid rgba(128, 128, 128, 0.3);")
            l.addWidget(color_box)

            # Rótulos informativos
            lbl_hex = QLabel(f"<b>{c['hex']}</b> ({c['percent']}%)")
            l.addWidget(lbl_hex)

            lbl_rgb = QLabel(c["rgb_str"])
            lbl_rgb.setStyleSheet("font-size: 11px; color: #888888;")
            l.addWidget(lbl_rgb)

            btn_copy = QPushButton("Copiar HEX")
            btn_copy.setFixedHeight(26)
            hex_val = c["hex"]
            btn_copy.clicked.connect(lambda _, h=hex_val: self._copy_single(h))
            l.addWidget(btn_copy)

            self.grid_colors.addWidget(card, idx // 3, idx % 3)

    def _copy_single(self, text: str):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copiado", f"Código {text} copiado para a área de transferência!")

    def _copy_css(self):
        if not self.extracted_colors:
            return
        css = export_palette_css(self.extracted_colors)
        QApplication.clipboard().setText(css)
        QMessageBox.information(self, "Copiado", "Variáveis CSS da paleta copiadas com sucesso!")

    def _copy_json(self):
        if not self.extracted_colors:
            return
        js = export_palette_json(self.extracted_colors)
        QApplication.clipboard().setText(js)
        QMessageBox.information(self, "Copiado", "JSON da paleta copiado com sucesso!")

    def _save_palette_image(self):
        if not self.extracted_colors:
            return
        dst_str, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Paleta como Imagem",
            "paleta_cores.png",
            "Imagens PNG (*.png)"
        )
        if dst_str:
            export_palette_image(self.extracted_colors, Path(dst_str))
            QMessageBox.information(self, "Salvo", f"Imagem da paleta salva em:\n{dst_str}")
