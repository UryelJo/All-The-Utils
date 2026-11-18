"""
Ferramenta: Otimizador e Compressor de Imagens Profissional.
Comprime e reduz o tamanho de arquivos em lote com estimativa em tempo real
e comparação visual de fidelidade.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.compress.logic import (
    COMPRESSION_MODES, compress_single_image,
    estimate_compressed_size, render_compress_preview
)
from wintoolbox.ui.widgets.live_preview import ImageLivePreviewPanel
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.compress.ui")


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
        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Coluna Esquerda: Controles e Estimativa
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        grp_opts = QGroupBox("Parâmetros de Compressão")
        grid = QGridLayout(grp_opts)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Modo de compressão:"), 0, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(COMPRESSION_MODES)
        self.cmb_mode.currentTextChanged.connect(self._on_mode_changed)
        grid.addWidget(self.cmb_mode, 0, 1)

        grid.addWidget(QLabel("Qualidade visual:"), 1, 0)
        self.slider_quality = SliderSpinControl("", 10, 100, 80, suffix="%")
        self.slider_quality.valueChanged.connect(self._on_params_changed)
        grid.addWidget(self.slider_quality, 1, 1)

        grid.addWidget(QLabel("Meta máxima (KB):"), 2, 0)
        self.spin_target_kb = SliderSpinControl("", 20, 5000, 300, step=10, suffix=" KB")
        self.spin_target_kb.valueChanged.connect(self._on_params_changed)
        grid.addWidget(self.spin_target_kb, 2, 1)

        # Checkboxes
        box_checks = QVBoxLayout()
        box_checks.setSpacing(6)
        self.chk_strip_exif = QCheckBox("Remover metadados EXIF (Economiza espaço)")
        self.chk_strip_exif.setChecked(True)
        self.chk_strip_exif.toggled.connect(self._on_params_changed)

        self.chk_quantize = QCheckBox("Quantizar PNG para 256 cores (Redução extrema)")
        self.chk_quantize.toggled.connect(self._on_params_changed)

        self.chk_progressive = QCheckBox("JPEG Progressivo (Carregamento mais rápido na web)")
        self.chk_progressive.setChecked(True)
        self.chk_progressive.toggled.connect(self._on_params_changed)

        box_checks.addWidget(self.chk_strip_exif)
        box_checks.addWidget(self.chk_quantize)
        box_checks.addWidget(self.chk_progressive)
        grid.addLayout(box_checks, 3, 0, 1, 2)

        left_layout.addWidget(grp_opts)

        # Card de Estimativa de Economia
        card_est = QFrame()
        card_est.setProperty("class", "card")
        card_est.setStyleSheet("QFrame { background-color: #1A1F26; border: 1px solid #2B3542; border-radius: 6px; padding: 10px; }")
        v_est = QVBoxLayout(card_est)
        v_est.setSpacing(4)

        lbl_est_title = QLabel("Estimativa de Tamanho e Economia:")
        lbl_est_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #57A5FF;")
        v_est.addWidget(lbl_est_title)

        self.lbl_estimation = QLabel("Adicione imagens para ver a estimativa de redução.")
        self.lbl_estimation.setStyleSheet("font-size: 12px; color: #E0E4E8;")
        v_est.addWidget(self.lbl_estimation)
        left_layout.addWidget(card_est)

        left_layout.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna Direita: Preview
        self.preview_panel = ImageLivePreviewPanel("Prévia", panel)
        self.preview_panel.set_preview_generator(render_compress_preview)
        main_layout.addWidget(self.preview_panel, stretch=1)

        self._active_file: Optional[Path] = None
        self._on_mode_changed(self.cmb_mode.currentText())
        panel.on_active_file_changed = self.on_active_file_changed
        return panel

    def on_active_file_changed(self, path: Path) -> None:
        self._active_file = path
        self.preview_panel.set_source_file(path)
        self._update_estimation_and_preview()

    def _on_mode_changed(self, mode: str) -> None:
        is_balanced = mode == "Qualidade Visual Balanceada"
        is_target = mode == "Meta de Tamanho Máximo (KB)"

        self.slider_quality.setEnabled(is_balanced)
        self.spin_target_kb.setEnabled(is_target)
        self._update_estimation_and_preview()

    def _on_params_changed(self, *_) -> None:
        self._update_estimation_and_preview()

    def _update_estimation_and_preview(self) -> None:
        params = self.get_options()
        self.preview_panel.update_params(params)

        if self._active_file and self._active_file.is_file():
            try:
                orig = self._active_file.stat().st_size
                est = estimate_compressed_size(self._active_file, params)
                saved = orig - est
                pct = max(0, int((saved / orig) * 100)) if orig > 0 else 0
                orig_kb = orig / 1024
                est_kb = est / 1024
                self.lbl_estimation.setText(
                    f"{self._active_file.name}:\n"
                    f"{orig_kb:.1f} KB → ~{est_kb:.1f} KB (Economia estimada: ~{pct}%)"
                )
            except Exception:
                self.lbl_estimation.setText("Estimativa em cálculo...")
        else:
            self.lbl_estimation.setText("Selecione uma imagem na lista para ver a estimativa.")

    def get_options(self) -> Dict[str, Any]:
        return {
            "mode": self.cmb_mode.currentText(),
            "quality": int(self.slider_quality.value()),
            "target_kb": int(self.spin_target_kb.value()),
            "strip_exif": self.chk_strip_exif.isChecked(),
            "quantize_png": self.chk_quantize.isChecked(),
            "progressive_jpeg": self.chk_progressive.isChecked(),
        }

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            orig_sz, new_sz = compress_single_image(src, dst, params)
            reduction = max(0, int(((orig_sz - new_sz) / orig_sz) * 100)) if orig_sz > 0 else 0
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"-{reduction}% ({orig_sz // 1024} KB → {new_sz // 1024} KB)",
                bytes_in=orig_sz,
                bytes_out=new_sz,
            )
        except Exception as exc:
            _log.warning("Falha ao comprimir imagem '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
