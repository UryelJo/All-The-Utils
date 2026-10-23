"""
Ferramenta: Conversor de Imagens em Lote.
Implementação completa herdando de FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.convert.logic import SUPPORTED_OUTPUTS, convert_single_image

@register
class ImageConverterTool(FileTool):
    id = "images.convert"
    name = "Conversor de Imagens"
    category = "Imagens"
    description = "Conversão de imagens individuais ou pastas completas (WEBP, JPG, PNG, ICO, PDF, etc.)"
    keywords = ["imagem", "foto", "converter", "webp", "jpeg", "png", "ico", "lote", "pasta"]
    accepts = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif", ".ico", ".heic", ".heif", ".avif"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Conversão")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        row = QHBoxLayout()
        row.setSpacing(12)

        # Formato de Saída
        lbl_fmt = QLabel("Formato de saída:")
        row.addWidget(lbl_fmt)

        self.cmb_format = QComboBox()
        self.cmb_format.addItems(SUPPORTED_OUTPUTS)
        self.cmb_format.setCurrentText("WEBP")
        self.cmb_format.currentTextChanged.connect(self._on_format_changed)
        row.addWidget(self.cmb_format)

        row.addSpacing(20)

        # Qualidade de Compressão
        self.lbl_quality = QLabel("Qualidade (90%):")
        row.addWidget(self.lbl_quality)

        self.slider_quality = QSlider(Qt.Horizontal)
        self.slider_quality.setRange(10, 100)
        self.slider_quality.setValue(90)
        self.slider_quality.setFixedWidth(140)
        self.slider_quality.valueChanged.connect(
            lambda v: self.lbl_quality.setText(f"Qualidade ({v}%):")
        )
        row.addWidget(self.slider_quality)

        row.addStretch()
        layout.addLayout(row)

        return panel

    def _on_format_changed(self, fmt: str):
        is_lossy = fmt in ("JPG", "WEBP")
        self.slider_quality.setEnabled(is_lossy)
        self.lbl_quality.setEnabled(is_lossy)

    def get_options(self) -> Dict[str, Any]:
        return {
            "format": self.cmb_format.currentText(),
            "quality": self.slider_quality.value()
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = params.get("format", "WEBP").lower()
        return f".{fmt}"

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            fmt = params.get("format", "WEBP")
            qual = params.get("quality", 90)
            convert_single_image(src, dst, target_format=fmt, quality=qual)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                bytes_in=src.stat().st_size,
                bytes_out=dst.stat().st_size if dst.exists() else 0
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                error=str(e)
            )
