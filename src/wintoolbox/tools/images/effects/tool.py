"""
Ferramenta: Filtros e Ajustes de Imagem em Lote com Preview Dinâmico.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.effects.logic import (
    IMAGE_EFFECTS, apply_image_effects_and_adjustments, render_effects_preview
)
from wintoolbox.ui.widgets.live_preview import ImageLivePreviewPanel
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.effects.ui")


@register
class ImageEffectsTool(FileTool):
    id = "images.effects"
    name = "Filtros e Ajustes de Imagem"
    category = "Imagens"
    description = "Ajuste brilho, contraste, saturação e aplique filtros artísticos (P&B, sépia, desfoque) em fotos"
    keywords = ["filtros", "ajustes", "brilho", "contraste", "saturacao", "sepia", "preto e branco", "desfoque", "fotos"]
    accepts = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".heic", ".heif", ".avif"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Coluna da Esquerda: Controles
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        grp_filters = QGroupBox("Filtros Artísticos e Efeitos")
        grid_f = QGridLayout(grp_filters)
        grid_f.setHorizontalSpacing(12)
        grid_f.setVerticalSpacing(8)

        grid_f.addWidget(QLabel("Filtro:"), 0, 0)
        self.cmb_effect = QComboBox()
        self.cmb_effect.addItems(IMAGE_EFFECTS)
        self.cmb_effect.currentTextChanged.connect(self._on_options_changed)
        grid_f.addWidget(self.cmb_effect, 0, 1)

        grid_f.addWidget(QLabel("Raio de desfoque:"), 1, 0)
        self.spin_blur = SliderSpinControl("", 0.5, 30.0, 2.5, step=0.5, decimals=1, suffix=" px")
        self.spin_blur.valueChanged.connect(self._on_options_changed)
        grid_f.addWidget(self.spin_blur, 1, 1)
        left_layout.addWidget(grp_filters)

        grp_adjusts = QGroupBox("Ajustes de Cor e Luz")
        grid_a = QGridLayout(grp_adjusts)
        grid_a.setHorizontalSpacing(12)
        grid_a.setVerticalSpacing(8)

        grid_a.addWidget(QLabel("Brilho:"), 0, 0)
        self.slider_brightness = SliderSpinControl("", 0.20, 2.50, 1.00, step=0.05, decimals=2, suffix="x")
        self.slider_brightness.valueChanged.connect(self._on_options_changed)
        grid_a.addWidget(self.slider_brightness, 0, 1)

        grid_a.addWidget(QLabel("Contraste:"), 1, 0)
        self.slider_contrast = SliderSpinControl("", 0.20, 2.50, 1.00, step=0.05, decimals=2, suffix="x")
        self.slider_contrast.valueChanged.connect(self._on_options_changed)
        grid_a.addWidget(self.slider_contrast, 1, 1)

        grid_a.addWidget(QLabel("Saturação:"), 2, 0)
        self.slider_saturation = SliderSpinControl("", 0.00, 2.50, 1.00, step=0.05, decimals=2, suffix="x")
        self.slider_saturation.valueChanged.connect(self._on_options_changed)
        grid_a.addWidget(self.slider_saturation, 2, 1)

        grid_a.addWidget(QLabel("Nitidez:"), 3, 0)
        self.slider_sharpness = SliderSpinControl("", 0.00, 3.00, 1.00, step=0.05, decimals=2, suffix="x")
        self.slider_sharpness.valueChanged.connect(self._on_options_changed)
        grid_a.addWidget(self.slider_sharpness, 3, 1)

        btn_reset = QPushButton("Redefinir Ajustes Padrão")
        btn_reset.setFixedHeight(26)
        btn_reset.clicked.connect(self._reset_adjustments)
        grid_a.addWidget(btn_reset, 4, 0, 1, 2)

        left_layout.addWidget(grp_adjusts)
        left_layout.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna da Direita: Preview
        self.preview_panel = ImageLivePreviewPanel("Prévia", panel)
        self.preview_panel.set_preview_generator(render_effects_preview)
        main_layout.addWidget(self.preview_panel, stretch=1)

        panel.on_active_file_changed = self.on_active_file_changed
        return panel

    def on_active_file_changed(self, path: Path) -> None:
        self.preview_panel.set_source_file(path)
        self._update_preview()

    def _on_options_changed(self, *_) -> None:
        is_blur = self.cmb_effect.currentText() == "Desfoque Gaussiano"
        self.spin_blur.setEnabled(is_blur)
        self._update_preview()

    def _reset_adjustments(self) -> None:
        self.cmb_effect.setCurrentText("Nenhum")
        self.slider_brightness.setValue(1.00)
        self.slider_contrast.setValue(1.00)
        self.slider_saturation.setValue(1.00)
        self.slider_sharpness.setValue(1.00)
        self.spin_blur.setValue(2.5)
        self._update_preview()

    def _update_preview(self) -> None:
        params = self.get_options()
        self.preview_panel.update_params(params)

    def get_options(self) -> Dict[str, Any]:
        return {
            "effect": self.cmb_effect.currentText(),
            "blur_radius": float(self.spin_blur.value()),
            "brightness": float(self.slider_brightness.value()),
            "contrast": float(self.slider_contrast.value()),
            "saturation": float(self.slider_saturation.value()),
            "sharpness": float(self.slider_sharpness.value()),
        }

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            bytes_in = src.stat().st_size
            apply_image_effects_and_adjustments(src, dst, params)
            bytes_out = dst.stat().st_size if dst.exists() else 0
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message="Filtros aplicados com sucesso",
                bytes_in=bytes_in,
                bytes_out=bytes_out,
            )
        except Exception as exc:
            _log.warning("Falha ao aplicar efeitos em '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
