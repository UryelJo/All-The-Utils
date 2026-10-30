"""
Ferramenta: Redimensionador e Cortador de Imagens em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.resize.logic import (
    FIT_MODES, RESAMPLE_FILTERS, RESIZE_MODES, ROTATION_OPTIONS,
    resize_single_image
)

@register
class ImageResizeTool(FileTool):
    id = "images.resize"
    name = "Redimensionador e Cortador de Imagens"
    category = "Imagens"
    description = "Redimensione, corte, rotacione e espelhe fotos e imagens em lote com alta qualidade"
    keywords = ["redimensionar", "imagem", "escala", "cortar", "crop", "rotacionar", "espelhar", "lanczos", "fotos"]
    accepts = [".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".tiff", ".tif", ".ico", ".heic", ".heif", ".hif", ".avif", ".qoi", ".tga", ".psd", ".jp2", ".dds"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Redimensionamento e Transformação")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 1. Modo de Redimensionamento
        grid.addWidget(QLabel("Modo de dimensionamento:"), 0, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(RESIZE_MODES)
        self.cmb_mode.currentTextChanged.connect(self._on_mode_changed)
        grid.addWidget(self.cmb_mode, 0, 1)

        # 2. Porcentagem
        self.lbl_percent = QLabel("Porcentagem (%):")
        grid.addWidget(self.lbl_percent, 0, 2)
        self.spin_percent = QSpinBox()
        self.spin_percent.setRange(1, 1000)
        self.spin_percent.setValue(50)
        self.spin_percent.setSuffix(" %")
        grid.addWidget(self.spin_percent, 0, 3)

        # 3. Largura e Altura
        self.lbl_width = QLabel("Largura alvo (px):")
        grid.addWidget(self.lbl_width, 1, 0)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(16, 16384)
        self.spin_width.setValue(1920)
        grid.addWidget(self.spin_width, 1, 1)

        self.lbl_height = QLabel("Altura alvo (px):")
        grid.addWidget(self.lbl_height, 1, 2)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(16, 16384)
        self.spin_height.setValue(1080)
        grid.addWidget(self.spin_height, 1, 3)

        # 4. Ajuste / Encaixe
        self.lbl_fit = QLabel("Comportamento de ajuste:")
        grid.addWidget(self.lbl_fit, 2, 0)
        self.cmb_fit = QComboBox()
        self.cmb_fit.addItems(FIT_MODES)
        grid.addWidget(self.cmb_fit, 2, 1)

        # 5. Algoritmo de Interpolação
        grid.addWidget(QLabel("Filtro de interpolação:"), 2, 2)
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(list(RESAMPLE_FILTERS.keys()))
        grid.addWidget(self.cmb_filter, 2, 3)

        # 6. Rotação e Espelhamento
        grid.addWidget(QLabel("Rotação:"), 3, 0)
        self.cmb_rotation = QComboBox()
        self.cmb_rotation.addItems(ROTATION_OPTIONS)
        grid.addWidget(self.cmb_rotation, 3, 1)

        box_flips = QHBoxLayout()
        self.chk_flip_h = QCheckBox("Espelhar Horizontal")
        self.chk_flip_v = QCheckBox("Espelhar Vertical")
        box_flips.addWidget(self.chk_flip_h)
        box_flips.addWidget(self.chk_flip_v)
        grid.addLayout(box_flips, 3, 2, 1, 2)

        layout.addLayout(grid)
        self._on_mode_changed(self.cmb_mode.currentText())

        return panel

    def _on_mode_changed(self, mode: str):
        is_pct = mode == "Porcentagem"
        is_exact = mode == "Caixa Exata (Largura x Altura)"
        is_w = mode == "Largura Máxima (Manter Proporção)"
        is_h = mode == "Altura Máxima (Manter Proporção)"

        self.lbl_percent.setVisible(is_pct)
        self.spin_percent.setVisible(is_pct)

        self.lbl_width.setVisible(not is_pct and not is_h)
        self.spin_width.setVisible(not is_pct and not is_h)

        self.lbl_height.setVisible(not is_pct and not is_w)
        self.spin_height.setVisible(not is_pct and not is_w)

        self.lbl_fit.setVisible(is_exact)
        self.cmb_fit.setVisible(is_exact)

    def get_options(self) -> Dict[str, Any]:
        return {
            "mode": self.cmb_mode.currentText(),
            "percent": self.spin_percent.value(),
            "width": self.spin_width.value(),
            "height": self.spin_height.value(),
            "keep_aspect": True,
            "fit_mode": self.cmb_fit.currentText(),
            "filter": self.cmb_filter.currentText(),
            "rotation": self.cmb_rotation.currentText(),
            "flip_h": self.chk_flip_h.isChecked(),
            "flip_v": self.chk_flip_v.isChecked()
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        # Mantém a extensão do arquivo original por padrão
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            ow, oh, nw, nh = resize_single_image(src, dst, params)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"Redimensionado de {ow}x{oh} para {nw}x{nh}"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                output_path=dst,
                error=f"Erro ao redimensionar: {str(e)}"
            )
