"""
Ferramenta: Otimizador e Compressor de Imagens.
Implementação completa herdando de FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QSlider, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.compress.logic import COMPRESSION_MODES, compress_single_image

@register
class ImageCompressorTool(FileTool):
    id = "images.compress"
    name = "Otimizador e Compressor de Imagens"
    category = "Imagens"
    description = "Comprima e reduza o peso de fotos PNG, JPG e WEBP sem perda perceptível de qualidade"
    keywords = ["comprimir", "otimizar", "reduzir", "tamanho", "peso", "lossless", "quantizacao", "jpeg", "png", "webp"]
    accepts = [".png", ".jpg", ".jpeg", ".jfif", ".webp", ".heic", ".heif", ".hif", ".avif"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Otimização e Compressão")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Modo de Compressão
        grid.addWidget(QLabel("Modo de compressão:"), 0, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(COMPRESSION_MODES)
        self.cmb_mode.currentTextChanged.connect(self._on_mode_changed)
        grid.addWidget(self.cmb_mode, 0, 1)

        # Qualidade (Slider)
        self.lbl_quality = QLabel("Qualidade (80%):")
        grid.addWidget(self.lbl_quality, 0, 2)

        self.slider_quality = QSlider(Qt.Horizontal)
        self.slider_quality.setRange(10, 100)
        self.slider_quality.setValue(80)
        self.slider_quality.valueChanged.connect(
            lambda v: self.lbl_quality.setText(f"Qualidade ({v}%):")
        )
        grid.addWidget(self.slider_quality, 0, 3)

        # Meta de Tamanho (KB)
        self.lbl_target = QLabel("Tamanho máximo desejado:")
        grid.addWidget(self.lbl_target, 1, 0)
        self.spin_target_kb = QSpinBox()
        self.spin_target_kb.setRange(20, 50000)
        self.spin_target_kb.setValue(300)
        self.spin_target_kb.setSuffix(" KB")
        grid.addWidget(self.spin_target_kb, 1, 1)

        # Checkboxes de otimização
        box_checks = QHBoxLayout()
        self.chk_strip_exif = QCheckBox("Remover Metadados EXIF (Economiza espaço)")
        self.chk_strip_exif.setChecked(True)
        self.chk_quantize = QCheckBox("Quantizar PNG (Paleta de 256 cores)")
        self.chk_progressive = QCheckBox("JPEG Progressivo")
        self.chk_progressive.setChecked(True)

        box_checks.addWidget(self.chk_strip_exif)
        box_checks.addWidget(self.chk_quantize)
        box_checks.addWidget(self.chk_progressive)
        grid.addLayout(box_checks, 2, 0, 1, 4)

        layout.addLayout(grid)
        self._on_mode_changed(self.cmb_mode.currentText())

        return panel

    def _on_mode_changed(self, mode: str):
        is_balanced = mode == "Qualidade Visual Balanceada"
        is_target = mode == "Meta de Tamanho Máximo (KB)"

        self.lbl_quality.setVisible(is_balanced)
        self.slider_quality.setVisible(is_balanced)

        self.lbl_target.setVisible(is_target)
        self.spin_target_kb.setVisible(is_target)

    def get_options(self) -> Dict[str, Any]:
        return {
            "mode": self.cmb_mode.currentText(),
            "quality": self.slider_quality.value(),
            "target_kb": self.spin_target_kb.value(),
            "strip_exif": self.chk_strip_exif.isChecked(),
            "quantize_png": self.chk_quantize.isChecked(),
            "progressive_jpeg": self.chk_progressive.isChecked()
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            sz_before, sz_after = compress_single_image(src, dst, params)
            diff_kb = (sz_before - sz_after) / 1024.0
            pct = ((sz_before - sz_after) / max(sz_before, 1)) * 100.0

            if diff_kb > 0:
                msg = f"Economia de {diff_kb:.1f} KB ({pct:.1f}% reduzido)"
            else:
                msg = f"Tamanho mantido ({sz_after / 1024:.1f} KB)"

            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=msg
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                output_path=dst,
                error=f"Erro na compressão: {str(e)}"
            )
