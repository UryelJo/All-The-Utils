"""
Ferramenta: Conversor Universal de Imagens em Lote (com suporte completo a iPhone HEIF/HEIC).
Implementação completa herdando de FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.convert.logic import (
    LOSSLESS_TOGGLE_FORMATS,
    LOSSY_CAPABLE_FORMATS,
    NO_ALPHA_FORMATS,
    PILLOW_FORMAT_MAP,
    SUBSAMPLING_CAPABLE_FORMATS,
    SUPPORTED_IMAGE_INPUTS,
    SUPPORTED_OUTPUTS,
    convert_single_image,
    get_output_extension,
)

_log = get_logger("images.convert.ui")


@register
class ImageConverterTool(FileTool):
    id = "images.convert"
    name = "Conversor de Imagens"
    category = "Imagens"
    description = (
        "Conversão em lote entre 42 formatos de entrada e 18 de saída "
        "(HEIC/HEIF de iPhone, AVIF, WEBP, JPG, PNG, QOI, PSD, TGA, DDS, JP2, ICNS, ICO, PDF)"
    )
    keywords = [
        "imagem", "foto", "converter", "heic", "heif", "hif", "iphone", "apple",
        "avif", "webp", "jpeg", "jpg", "png", "ico", "icns", "qoi", "psd", "tga",
        "dds", "jp2", "tiff", "gif", "pdf", "lote", "pasta", "display p3", "srgb",
    ]
    accepts = list(SUPPORTED_IMAGE_INPUTS)
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Conversão, Cores e Metadados")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Linha 0: Formato de saída + Qualidade + Lossless
        grid.addWidget(QLabel("Formato de saída:"), 0, 0)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(SUPPORTED_OUTPUTS)
        self.cmb_format.setCurrentText("WEBP")
        self.cmb_format.currentTextChanged.connect(self._sync_controls_state)
        grid.addWidget(self.cmb_format, 0, 1)

        qual_row = QHBoxLayout()
        qual_row.setSpacing(10)
        self.lbl_quality = QLabel("Qualidade (90%):")
        qual_row.addWidget(self.lbl_quality)

        self.slider_quality = QSlider(Qt.Horizontal)
        self.slider_quality.setRange(10, 100)
        self.slider_quality.setValue(90)
        self.slider_quality.setMinimumWidth(130)
        self.slider_quality.valueChanged.connect(
            lambda v: self.lbl_quality.setText(f"Qualidade ({v}%):")
        )
        qual_row.addWidget(self.slider_quality)

        self.chk_lossless = QCheckBox("Sem perdas (Lossless)")
        self.chk_lossless.toggled.connect(self._sync_controls_state)
        qual_row.addWidget(self.chk_lossless)
        qual_row.addStretch()
        grid.addLayout(qual_row, 0, 2, 1, 2)

        # Linha 1: Subsampling de Croma + Perfil de Cores ICC (iPhone Display P3)
        grid.addWidget(QLabel("Amostragem de croma:"), 1, 0)
        self.cmb_subsampling = QComboBox()
        self.cmb_subsampling.addItem("4:2:0 (Padrão - Menor arquivo)", "4:2:0")
        self.cmb_subsampling.addItem("4:2:2 (Intermediário)", "4:2:2")
        self.cmb_subsampling.addItem("4:4:4 (Máxima nitidez de cores)", "4:4:4")
        grid.addWidget(self.cmb_subsampling, 1, 1)

        grid.addWidget(QLabel("Perfil de cor (Display P3 / ICC):"), 1, 2)
        self.cmb_color_profile = QComboBox()
        self.cmb_color_profile.addItem("Converter para sRGB (Recomendado Windows/Web)", "srgb")
        self.cmb_color_profile.addItem("Preservar perfil ICC original", "preserve")
        self.cmb_color_profile.addItem("Remover perfil ICC", "strip")
        grid.addWidget(self.cmb_color_profile, 1, 3)

        # Linha 2: Metadados EXIF + Cor de Fundo para Transparência
        grid.addWidget(QLabel("Metadados EXIF:"), 2, 0)
        self.cmb_exif = QComboBox()
        self.cmb_exif.addItem("Preservar EXIF (Data, Câmera e GPS)", "preserve")
        self.cmb_exif.addItem("Preservar Data/Câmera (Remover GPS)", "strip_gps")
        self.cmb_exif.addItem("Remover todos os metadados", "strip_all")
        grid.addWidget(self.cmb_exif, 2, 1)

        grid.addWidget(QLabel("Fundo (formatos sem transparência):"), 2, 2)
        self.cmb_bg_color = QComboBox()
        self.cmb_bg_color.addItem("Branco (#FFFFFF)", "#FFFFFF")
        self.cmb_bg_color.addItem("Preto (#000000)", "#000000")
        self.cmb_bg_color.addItem("Cinza Neutro (#808080)", "#808080")
        grid.addWidget(self.cmb_bg_color, 2, 3)

        # Linha 3: Multi-quadro / Sequências HEIC
        self.chk_all_frames = QCheckBox(
            "Extrair todos os quadros em arquivos multi-imagem (sequências HEIC / bursts / TIFF / GIF)"
        )
        grid.addWidget(self.chk_all_frames, 3, 0, 1, 4)

        layout.addLayout(grid)
        self._sync_controls_state()
        return panel

    def _sync_controls_state(self) -> None:
        fmt = self.cmb_format.currentText().upper()
        pillow_fmt = PILLOW_FORMAT_MAP.get(fmt, fmt)

        can_toggle_lossless = fmt in LOSSLESS_TOGGLE_FORMATS
        self.chk_lossless.setEnabled(can_toggle_lossless)
        is_lossless_active = can_toggle_lossless and self.chk_lossless.isChecked()

        is_lossy_slider_active = (fmt in LOSSY_CAPABLE_FORMATS) and not is_lossless_active
        self.slider_quality.setEnabled(is_lossy_slider_active)
        self.lbl_quality.setEnabled(is_lossy_slider_active)

        can_subsample = (fmt in SUBSAMPLING_CAPABLE_FORMATS) and not is_lossless_active
        self.cmb_subsampling.setEnabled(can_subsample)

        self.cmb_bg_color.setEnabled(pillow_fmt in NO_ALPHA_FORMATS)

    def get_options(self) -> Dict[str, Any]:
        fmt = self.cmb_format.currentText().upper()
        lossless = (fmt in LOSSLESS_TOGGLE_FORMATS) and self.chk_lossless.isChecked()
        return {
            "format": fmt,
            "quality": self.slider_quality.value(),
            "lossless": lossless,
            "subsampling": self.cmb_subsampling.currentData() or "4:2:0",
            "color_profile_mode": self.cmb_color_profile.currentData() or "srgb",
            "exif_mode": self.cmb_exif.currentData() or "preserve",
            "bg_color": self.cmb_bg_color.currentData() or "#FFFFFF",
            "extract_all_frames": self.chk_all_frames.isChecked(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = str(params.get("format", "WEBP"))
        return get_output_extension(fmt)

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            generated = convert_single_image(
                source_path=src,
                output_path=dst,
                target_format=str(params.get("format", "WEBP")),
                quality=int(params.get("quality", 90)),
                lossless=bool(params.get("lossless", False)),
                subsampling=str(params.get("subsampling", "4:2:0")),
                color_profile_mode=str(params.get("color_profile_mode", "srgb")),
                exif_mode=str(params.get("exif_mode", "preserve")),
                bg_color=str(params.get("bg_color", "#FFFFFF")),
                extract_all_frames=bool(params.get("extract_all_frames", False)),
            )
            total_out = sum(p.stat().st_size for p in generated if p.exists())
            msg = (
                f"Convertido ({len(generated)} quadros gerados)"
                if len(generated) > 1
                else "Convertido com sucesso"
            )
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=msg,
                bytes_in=src.stat().st_size,
                bytes_out=total_out,
            )
        except Exception as exc:
            _log.warning("Falha ao converter imagem '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
