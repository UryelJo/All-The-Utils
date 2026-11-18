"""
Ferramenta: Redimensionador e Cortador de Imagens Profissional em Lote.
Integra redimensionamento inteligente, corte visual com proporções pré-definidas,
rotação fina e pré-visualização dinâmica em tempo real.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.resize.logic import (
    ASPECT_RATIOS, FIT_MODES, RESAMPLE_FILTERS, RESIZE_MODES, ROTATION_OPTIONS,
    render_resize_preview, resize_single_image
)
from wintoolbox.ui.widgets.live_preview import ImageLivePreviewPanel
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.resize.ui")


@register
class ImageResizeTool(FileTool):
    id = "images.resize"
    name = "Redimensionador e Cortador de Imagens"
    category = "Imagens"
    description = "Redimensione, corte com proporções exatas, rotacione e ajuste fotos e imagens em lote com preview dinâmico"
    keywords = ["redimensionar", "imagem", "escala", "cortar", "crop", "rotacionar", "espelhar", "proporção", "fotos", "lote"]
    accepts = [".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".tiff", ".tif", ".ico", ".heic", ".heif", ".hif", ".avif", ".qoi", ".tga", ".psd", ".jp2", ".dds"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Coluna da Esquerda: Controles organizados por Grupos
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # Grupo 1: Dimensionamento e Escala
        grp_dim = QGroupBox("1. Dimensionamento e Escala")
        grid_dim = QGridLayout(grp_dim)
        grid_dim.setHorizontalSpacing(12)
        grid_dim.setVerticalSpacing(8)

        grid_dim.addWidget(QLabel("Modo:"), 0, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(RESIZE_MODES)
        self.cmb_mode.currentTextChanged.connect(self._on_options_changed)
        grid_dim.addWidget(self.cmb_mode, 0, 1)

        self.lbl_percent = QLabel("Porcentagem:")
        grid_dim.addWidget(self.lbl_percent, 0, 2)
        self.spin_percent = SliderSpinControl("", 1, 500, 50, suffix="%")
        self.spin_percent.valueChanged.connect(self._on_options_changed)
        grid_dim.addWidget(self.spin_percent, 0, 3)

        self.lbl_width = QLabel("Largura (px):")
        grid_dim.addWidget(self.lbl_width, 1, 0)
        self.spin_width = QSpinBox()
        self.spin_width.setFixedWidth(80)
        self.spin_width.setRange(16, 16384)
        self.spin_width.setValue(1920)
        self.spin_width.valueChanged.connect(self._on_options_changed)
        grid_dim.addWidget(self.spin_width, 1, 1)

        self.lbl_height = QLabel("Altura (px):")
        grid_dim.addWidget(self.lbl_height, 1, 2)
        self.spin_height = QSpinBox()
        self.spin_height.setFixedWidth(80)
        self.spin_height.setRange(16, 16384)
        self.spin_height.setValue(1080)
        self.spin_height.valueChanged.connect(self._on_options_changed)
        grid_dim.addWidget(self.spin_height, 1, 3)

        self.lbl_fit = QLabel("Comportamento:")
        grid_dim.addWidget(self.lbl_fit, 2, 0)
        self.cmb_fit = QComboBox()
        self.cmb_fit.addItems(FIT_MODES)
        self.cmb_fit.currentTextChanged.connect(self._on_options_changed)
        grid_dim.addWidget(self.cmb_fit, 2, 1)

        grid_dim.addWidget(QLabel("Filtro:"), 2, 2)
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(list(RESAMPLE_FILTERS.keys()))
        self.cmb_filter.currentTextChanged.connect(self._on_options_changed)
        grid_dim.addWidget(self.cmb_filter, 2, 3)

        left_layout.addWidget(grp_dim)

        # Grupo 2: Recorte Visual Interativo
        grp_crop = QGroupBox("2. Recorte Visual (Crop)")
        v_crop = QVBoxLayout(grp_crop)
        v_crop.setSpacing(8)

        row_crop_ctrls = QHBoxLayout()
        self.chk_enable_crop = QCheckBox("Ativar corte visual")
        self.chk_enable_crop.toggled.connect(self._on_crop_toggled)
        row_crop_ctrls.addWidget(self.chk_enable_crop)

        row_crop_ctrls.addWidget(QLabel("Proporção:"))
        self.cmb_aspect = QComboBox()
        self.cmb_aspect.addItems(list(ASPECT_RATIOS.keys()))
        self.cmb_aspect.currentTextChanged.connect(self._on_aspect_changed)
        row_crop_ctrls.addWidget(self.cmb_aspect)

        self.btn_reset_crop = QPushButton("Limpar Corte")
        self.btn_reset_crop.setFixedHeight(24)
        self.btn_reset_crop.clicked.connect(self._on_reset_crop)
        row_crop_ctrls.addWidget(self.btn_reset_crop)
        row_crop_ctrls.addStretch()
        v_crop.addLayout(row_crop_ctrls)

        self.lbl_crop_info = QLabel("Dica: Com o corte ativado, arraste sobre a imagem à direita para selecionar a área.")
        self.lbl_crop_info.setStyleSheet("color: #8F96A0; font-size: 11px;")
        v_crop.addWidget(self.lbl_crop_info)

        left_layout.addWidget(grp_crop)

        # Grupo 3: Rotação e Espelhamento
        grp_rot = QGroupBox("3. Rotação e Espelhamento")
        grid_rot = QGridLayout(grp_rot)
        grid_rot.setHorizontalSpacing(12)
        grid_rot.setVerticalSpacing(8)

        grid_rot.addWidget(QLabel("Rotação 90°:"), 0, 0)
        self.cmb_rotation = QComboBox()
        self.cmb_rotation.addItems(ROTATION_OPTIONS)
        self.cmb_rotation.currentTextChanged.connect(self._on_options_changed)
        grid_rot.addWidget(self.cmb_rotation, 0, 1)

        grid_rot.addWidget(QLabel("Rotação fina:"), 0, 2)
        self.spin_fine_rot = SliderSpinControl("", -45, 45, 0, step=0.5, decimals=1, suffix="°")
        self.spin_fine_rot.valueChanged.connect(self._on_options_changed)
        grid_rot.addWidget(self.spin_fine_rot, 0, 3)

        box_flips = QHBoxLayout()
        self.chk_flip_h = QCheckBox("Espelhar Horizontal")
        self.chk_flip_h.toggled.connect(self._on_options_changed)
        self.chk_flip_v = QCheckBox("Espelhar Vertical")
        self.chk_flip_v.toggled.connect(self._on_options_changed)
        box_flips.addWidget(self.chk_flip_h)
        box_flips.addWidget(self.chk_flip_v)
        box_flips.addStretch()
        grid_rot.addLayout(box_flips, 1, 0, 1, 4)

        left_layout.addWidget(grp_rot)
        left_layout.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna da Direita: Preview Interativo
        self.preview_panel = ImageLivePreviewPanel("Pré-visualização Dinâmica", panel)
        self.preview_panel.set_preview_generator(render_resize_preview)
        self.preview_panel.canvas.roiChanged.connect(self._on_canvas_roi_changed)
        main_layout.addWidget(self.preview_panel, stretch=1)

        self._current_crop_box: Optional[Tuple[int, int, int, int]] = None
        self._sync_mode_visibility()
        panel.on_active_file_changed = self.on_active_file_changed
        return panel

    def on_active_file_changed(self, path: Path) -> None:
        self.preview_panel.set_source_file(path)
        self._update_preview()

    def _on_options_changed(self, *_) -> None:
        self._sync_mode_visibility()
        self._update_preview()

    def _sync_mode_visibility(self) -> None:
        mode = self.cmb_mode.currentText()
        is_pct = mode == "Porcentagem"
        is_box = mode == "Caixa Exata (Largura x Altura)"

        self.spin_percent.setVisible(is_pct)
        self.lbl_percent.setVisible(is_pct)

        self.spin_width.setVisible(not is_pct)
        self.lbl_width.setVisible(not is_pct)
        self.spin_height.setVisible(not is_pct and mode != "Largura Máxima (Manter Proporção)")
        self.lbl_height.setVisible(not is_pct and mode != "Largura Máxima (Manter Proporção)")

        self.lbl_fit.setVisible(is_box)
        self.cmb_fit.setVisible(is_box)

    def _on_crop_toggled(self, checked: bool) -> None:
        self.preview_panel.canvas.set_roi_selection_enabled(checked)
        if not checked:
            self._current_crop_box = None
            self.preview_panel.canvas.clear_roi()
        self._update_preview()

    def _on_aspect_changed(self, text: str) -> None:
        if not self.chk_enable_crop.isChecked():
            self.chk_enable_crop.setChecked(True)

        ratio = ASPECT_RATIOS.get(text)
        if ratio and self.preview_panel._cached_original_pixmap:
            p = self.preview_panel._cached_original_pixmap
            rw, rh = ratio
            target_ratio = rw / rh
            box_w = int(p.width() * 0.85)
            box_h = int(box_w / target_ratio)
            if box_h > int(p.height() * 0.85):
                box_h = int(p.height() * 0.85)
                box_w = int(box_h * target_ratio)
            x1 = (p.width() - box_w) // 2
            y1 = (p.height() - box_h) // 2
            rect = QRect(x1, y1, box_w, box_h)
            self.preview_panel.canvas.set_roi(rect)
            self._current_crop_box = (x1, y1, x1 + box_w, y1 + box_h)
            self._update_preview()

    def _on_reset_crop(self) -> None:
        self._current_crop_box = None
        self.preview_panel.canvas.clear_roi()
        self._update_preview()

    def _on_canvas_roi_changed(self, rect: QRect) -> None:
        if self.chk_enable_crop.isChecked() and not rect.isEmpty():
            self._current_crop_box = (rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())
            self._update_preview()

    def _update_preview(self) -> None:
        params = self.get_options()
        self.preview_panel.update_params(params)

    def get_options(self) -> Dict[str, Any]:
        return {
            "mode": self.cmb_mode.currentText(),
            "percent": int(self.spin_percent.value()),
            "width": self.spin_width.value(),
            "height": self.spin_height.value(),
            "fit_mode": self.cmb_fit.currentText(),
            "filter": self.cmb_filter.currentText(),
            "rotation": self.cmb_rotation.currentText(),
            "fine_rotation": float(self.spin_fine_rot.value()),
            "flip_h": self.chk_flip_h.isChecked(),
            "flip_v": self.chk_flip_v.isChecked(),
            "crop_box": self._current_crop_box if self.chk_enable_crop.isChecked() else None,
            "keep_aspect": True,
        }

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            bytes_in = src.stat().st_size
            ow, oh, nw, nh = resize_single_image(src, dst, params)
            bytes_out = dst.stat().st_size if dst.exists() else 0
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"{ow}×{oh} → {nw}×{nh} px",
                bytes_in=bytes_in,
                bytes_out=bytes_out,
            )
        except Exception as exc:
            _log.warning("Falha ao redimensionar imagem '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
