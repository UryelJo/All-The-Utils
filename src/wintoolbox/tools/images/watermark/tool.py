"""
Ferramenta: Aplicador de Marca d'Água Profissional em Lote.
Implementação completa com seleção explícita de Texto vs Logo (PNG)
e pré-visualização interativa em tempo real.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.watermark.logic import (
    WATERMARK_POSITIONS, apply_watermark_to_image, render_watermark_preview
)
from wintoolbox.ui.widgets.live_preview import ImageLivePreviewPanel
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.watermark.ui")


@register
class ImageWatermarkTool(FileTool):
    id = "images.watermark"
    name = "Aplicador de Marca d'Água"
    category = "Imagens"
    description = "Aplique assinaturas de texto ou logos em fotos em lote com controle de transparência e posição"
    keywords = ["marca", "dagua", "watermark", "logo", "assinatura", "copyright", "fotos", "texto", "lote"]
    accepts = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".heic", ".heif", ".avif"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Coluna da Esquerda: Controles com Abas Texto / Imagem
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Opções Comuns no Topo (Posição, Opacidade, Margem)
        card_common = QFrame()
        grid_common = QGridLayout(card_common)
        grid_common.setContentsMargins(0, 0, 0, 0)
        grid_common.setHorizontalSpacing(12)
        grid_common.setVerticalSpacing(8)

        grid_common.addWidget(QLabel("Posicionamento:"), 0, 0)
        self.cmb_pos = QComboBox()
        self.cmb_pos.addItems(WATERMARK_POSITIONS)
        self.cmb_pos.currentTextChanged.connect(self._on_options_changed)
        grid_common.addWidget(self.cmb_pos, 0, 1)

        grid_common.addWidget(QLabel("Opacidade:"), 0, 2)
        self.slider_opacity = SliderSpinControl("", 5, 100, 50, suffix="%")
        self.slider_opacity.valueChanged.connect(self._on_options_changed)
        grid_common.addWidget(self.slider_opacity, 0, 3)

        grid_common.addWidget(QLabel("Margem (px):"), 1, 0)
        self.spin_margin = SliderSpinControl("", 0, 300, 25, suffix=" px")
        self.spin_margin.valueChanged.connect(self._on_options_changed)
        grid_common.addWidget(self.spin_margin, 1, 1)

        left_layout.addWidget(card_common)

        # Abas explícitas: Texto vs Imagem (Logo)
        self.tabs_type = QTabWidget()
        self.tabs_type.currentChanged.connect(self._on_options_changed)

        # Aba 1: Marca d'Água em Texto
        tab_text = QWidget()
        grid_text = QGridLayout(tab_text)
        grid_text.setSpacing(8)

        grid_text.addWidget(QLabel("Texto da marca:"), 0, 0)
        self.txt_watermark = QLineEdit("© Minha Marca")
        self.txt_watermark.textChanged.connect(self._on_options_changed)
        grid_text.addWidget(self.txt_watermark, 0, 1, 1, 2)

        grid_text.addWidget(QLabel("Tamanho da fonte:"), 1, 0)
        self.spin_font_size = SliderSpinControl("", 10, 250, 42, suffix=" pt")
        self.spin_font_size.valueChanged.connect(self._on_options_changed)
        grid_text.addWidget(self.spin_font_size, 1, 1, 1, 2)

        grid_text.addWidget(QLabel("Cor do texto:"), 2, 0)
        row_color = QHBoxLayout()
        self.txt_color = QLineEdit("#FFFFFF")
        self.txt_color.setFixedWidth(80)
        self.txt_color.textChanged.connect(self._on_options_changed)
        btn_pick_color = QPushButton("Escolher...")
        btn_pick_color.clicked.connect(self._pick_color)
        row_color.addWidget(self.txt_color)
        row_color.addWidget(btn_pick_color)
        row_color.addStretch()
        grid_text.addLayout(row_color, 2, 1, 1, 2)

        grid_text.addWidget(QLabel("Rotação:"), 3, 0)
        self.spin_rotation = SliderSpinControl("", -90, 90, 0, suffix="°")
        self.spin_rotation.valueChanged.connect(self._on_options_changed)
        grid_text.addWidget(self.spin_rotation, 3, 1, 1, 2)

        self.tabs_type.addTab(tab_text, "Marca d'Água em Texto")

        # Aba 2: Imagem / Logo (PNG)
        tab_logo = QWidget()
        grid_logo = QGridLayout(tab_logo)
        grid_logo.setSpacing(8)

        grid_logo.addWidget(QLabel("Arquivo do Logo:"), 0, 0)
        row_logo = QHBoxLayout()
        self.txt_logo = QLineEdit()
        self.txt_logo.setPlaceholderText("Selecione um logo PNG transparente...")
        self.txt_logo.textChanged.connect(self._on_options_changed)
        btn_browse_logo = QPushButton("Procurar Logo...")
        btn_browse_logo.setProperty("class", "primary")
        btn_browse_logo.clicked.connect(self._browse_logo)
        row_logo.addWidget(self.txt_logo, stretch=1)
        row_logo.addWidget(btn_browse_logo)
        grid_logo.addLayout(row_logo, 0, 1)

        grid_logo.addWidget(QLabel("Escala do logo:"), 1, 0)
        self.spin_logo_scale = SliderSpinControl("", 5, 100, 25, suffix="%")
        self.spin_logo_scale.valueChanged.connect(self._on_options_changed)
        grid_logo.addWidget(self.spin_logo_scale, 1, 1)

        self.tabs_type.addTab(tab_logo, "Imagem / Logo (PNG)")
        left_layout.addWidget(self.tabs_type)

        left_layout.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna da Direita: Preview Dinâmico
        self.preview_panel = ImageLivePreviewPanel("Prévia da Marca d'Água", panel)
        self.preview_panel.set_preview_generator(render_watermark_preview)
        main_layout.addWidget(self.preview_panel, stretch=1)

        return panel

    def on_active_file_changed(self, path: Path) -> None:
        self.preview_panel.set_source_file(path)
        self._update_preview()

    def _on_options_changed(self, *_) -> None:
        if not hasattr(self, "preview_panel") or self.preview_panel is None:
            return
        self._update_preview()

    def _update_preview(self) -> None:
        if not hasattr(self, "preview_panel") or self.preview_panel is None:
            return
        params = self.get_options()
        self.preview_panel.update_params(params)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor()
        if c.isValid():
            self.txt_color.setText(c.name().upper())

    def _browse_logo(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Logo de Marca d'Água",
            "",
            "Imagens com Transparência (*.png *.webp *.gif *.svg *.ico)"
        )
        if f:
            self.txt_logo.setText(f)

    def get_options(self) -> Dict[str, Any]:
        wm_type = "Texto"
        if hasattr(self, "tabs_type") and self.tabs_type:
            wm_type = "Texto" if self.tabs_type.currentIndex() == 0 else "Imagem (Logo)"

        return {
            "type": wm_type,
            "position": self.cmb_pos.currentText() if hasattr(self, "cmb_pos") and self.cmb_pos else "Inferior Direito",
            "opacity": int(self.slider_opacity.value()) if hasattr(self, "slider_opacity") and self.slider_opacity else 50,
            "margin": int(self.spin_margin.value()) if hasattr(self, "spin_margin") and self.spin_margin else 25,
            "text": self.txt_watermark.text().strip() if hasattr(self, "txt_watermark") and self.txt_watermark else "All the Utils",
            "font_size": int(self.spin_font_size.value()) if hasattr(self, "spin_font_size") and self.spin_font_size else 42,
            "color": self.txt_color.text().strip() if hasattr(self, "txt_color") and self.txt_color else "#FFFFFF",
            "rotation": int(self.spin_rotation.value()) if hasattr(self, "spin_rotation") and self.spin_rotation else 0,
            "logo_path": self.txt_logo.text().strip() if hasattr(self, "txt_logo") and self.txt_logo else "",
            "logo_scale": int(self.spin_logo_scale.value()) if hasattr(self, "spin_logo_scale") and self.spin_logo_scale else 25,
        }

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            bytes_in = src.stat().st_size
            apply_watermark_to_image(src, dst, params)
            bytes_out = dst.stat().st_size if dst.exists() else 0
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message="Marca d'água aplicada com sucesso",
                bytes_in=bytes_in,
                bytes_out=bytes_out,
            )
        except Exception as exc:
            _log.warning("Falha ao aplicar marca d'água em '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
