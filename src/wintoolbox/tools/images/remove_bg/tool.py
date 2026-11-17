"""
Ferramenta: Removedor de Fundo de Imagem (Transparência PNG e Substituição).
Interface profissional com extração de paleta de cores dominante,
substituição de fundo por cor sólida ou imagem e preview em tempo real com zoom.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.palette.logic import extract_dominant_colors
from wintoolbox.tools.images.remove_bg.logic import (
    remove_image_background, render_remove_bg_preview
)
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.zoomable_image import ZoomableImageCanvas


@register
class RemoveBgTool(Tool):
    id = "images.remove_bg"
    name = "Removedor de Fundo de Imagem"
    category = "Imagens"
    description = "Remoção de fundo sólido, branco ou chroma key com canal alfa transparente ou troca de fundo"
    keywords = ["fundo", "removebg", "transparência", "png", "alpha", "chromakey", "recorte", "imagem"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RemoveBgView(self, parent)


class RemoveBgView(QWidget):
    def __init__(self, tool: RemoveBgTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_src_path: Optional[Path] = None
        self._custom_color: Tuple[int, int, int] = (0, 255, 0)
        self._solid_replacement_color: Tuple[int, int, int] = (255, 255, 255)
        self._custom_bg_image: Optional[Path] = None

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._do_update_preview)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra Superior: Carregamento
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.txt_src = QLineEdit()
        self.txt_src.setPlaceholderText("Selecione uma imagem de origem...")
        top_bar.addWidget(self.txt_src, stretch=1)

        btn_browse_src = QPushButton("Procurar Imagem...")
        btn_browse_src.setProperty("class", "primary")
        btn_browse_src.clicked.connect(self._on_browse_src)
        top_bar.addWidget(btn_browse_src)

        btn_paste = QPushButton("Colar Imagem")
        btn_paste.clicked.connect(self._on_paste_clipboard)
        top_bar.addWidget(btn_paste)

        btn_save = QPushButton("Salvar Resultado...")
        btn_save.setFixedHeight(32)
        btn_save.clicked.connect(self._on_save_result)
        top_bar.addWidget(btn_save)

        layout.addLayout(top_bar)

        # Configurações de Remoção e Paleta
        grp_cfg = QGroupBox("Configurações de Remoção e Cores Detectadas")
        v_cfg = QVBoxLayout(grp_cfg)
        v_cfg.setSpacing(8)

        row_ctrls = QHBoxLayout()
        row_ctrls.setSpacing(10)

        row_ctrls.addWidget(QLabel("Modo de detecção:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Detecção Automática nos Cantos", "auto_corners")
        self.cmb_mode.addItem("Fundo Branco / Claro", "white")
        self.cmb_mode.addItem("Fundo Preto / Escuro", "black")
        self.cmb_mode.addItem("Cor Específica (Chroma Key)", "custom")
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        row_ctrls.addWidget(self.cmb_mode)

        row_ctrls.addWidget(QLabel("Tolerância:"))
        self.slider_tol = SliderSpinControl("", 5, 120, 35)
        self.slider_tol.valueChanged.connect(self._request_preview)
        row_ctrls.addWidget(self.slider_tol)

        row_ctrls.addWidget(QLabel("Suavização (Feather):"))
        self.slider_feather = SliderSpinControl("", 0, 30, 8, suffix=" px")
        self.slider_feather.valueChanged.connect(self._request_preview)
        row_ctrls.addWidget(self.slider_feather)

        row_ctrls.addWidget(QLabel("Fundo final:"))
        self.cmb_bg_replace = QComboBox()
        self.cmb_bg_replace.addItem("Transparente (PNG)", "transparent")
        self.cmb_bg_replace.addItem("Cor Sólida", "solid")
        self.cmb_bg_replace.addItem("Outra Imagem de Fundo", "custom_image")
        self.cmb_bg_replace.currentIndexChanged.connect(self._on_replace_mode_changed)
        row_ctrls.addWidget(self.cmb_bg_replace)

        self.btn_pick_solid = QPushButton("Escolher Cor...")
        self.btn_pick_solid.setVisible(False)
        self.btn_pick_solid.clicked.connect(self._on_pick_solid_color)
        row_ctrls.addWidget(self.btn_pick_solid)

        self.btn_browse_bg_img = QPushButton("Escolher Fundo...")
        self.btn_browse_bg_img.setVisible(False)
        self.btn_browse_bg_img.clicked.connect(self._on_browse_bg_image)
        row_ctrls.addWidget(self.btn_browse_bg_img)

        row_ctrls.addStretch()
        v_cfg.addLayout(row_ctrls)

        # Paleta de Cores Dominantes
        self.row_palette = QHBoxLayout()
        self.row_palette.setSpacing(6)
        self.lbl_palette = QLabel("Cores detectadas (clique para remover):")
        self.lbl_palette.setStyleSheet("font-size: 11px; color: #8F96A0;")
        self.row_palette.addWidget(self.lbl_palette)
        self.palette_container = QWidget()
        self.palette_layout = QHBoxLayout(self.palette_container)
        self.palette_layout.setContentsMargins(0, 0, 0, 0)
        self.palette_layout.setSpacing(6)
        self.row_palette.addWidget(self.palette_container)
        self.row_palette.addStretch()
        v_cfg.addLayout(self.row_palette)

        layout.addWidget(grp_cfg)

        # Painel Central Dividido: Preview Original vs Preview Resultado
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        grp_orig = QGroupBox("Imagem Original")
        v_orig = QVBoxLayout(grp_orig)
        self.canvas_orig = ZoomableImageCanvas(self)
        v_orig.addWidget(self.canvas_orig)
        split_layout.addWidget(grp_orig, stretch=1)

        grp_res = QGroupBox("Resultado com Transparência (Ao Vivo)")
        v_res = QVBoxLayout(grp_res)
        self.canvas_res = ZoomableImageCanvas(self)
        self.canvas_res.set_checkerboard_enabled(True)
        v_res.addWidget(self.canvas_res)
        split_layout.addWidget(grp_res, stretch=1)

        layout.addLayout(split_layout)

    def _on_browse_src(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.heic *.avif);;Todos (*.*)"
        )
        if f:
            self._load_image(Path(f))

    def _on_paste_clipboard(self):
        clipboard = QApplication.clipboard()
        img = clipboard.image()
        if img.isNull():
            QMessageBox.warning(self, "Aviso", "A área de transferência não contém uma imagem válida.")
            return

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        img.save(str(tmp_path), "PNG")
        self._load_image(tmp_path)

    def _load_image(self, path: Path):
        self._current_src_path = path
        self.txt_src.setText(str(path))
        pix = QPixmap(str(path))
        self.canvas_orig.set_pixmap(pix, auto_fit=True)

        # Extrai paleta de cores dominante
        try:
            colors = extract_dominant_colors(path, num_colors=8)
            self._update_palette_buttons(colors)
        except Exception:
            pass

        self._request_preview()

    def _update_palette_buttons(self, colors: List[dict]):
        # Limpa botões antigos
        while self.palette_layout.count() > 0:
            item = self.palette_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for c in colors:
            hex_str = c["hex"]
            rgb_val = c["rgb"]
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"background-color: {hex_str}; border-radius: 4px; border: 1px solid #777;")
            btn.setToolTip(f"Usar {hex_str} como cor de fundo para remover")
            btn.clicked.connect(lambda _, rgb=rgb_val: self._on_select_palette_color(rgb))
            self.palette_layout.addWidget(btn)

    def _on_select_palette_color(self, rgb: Tuple[int, int, int]):
        self._custom_color = rgb
        self.cmb_mode.setCurrentIndex(3)  # Chroma Key
        self._request_preview()

    def _on_mode_changed(self):
        self._request_preview()

    def _on_replace_mode_changed(self):
        mode = self.cmb_bg_replace.currentData()
        self.btn_pick_solid.setVisible(mode == "solid")
        self.btn_browse_bg_img.setVisible(mode == "custom_image")
        self._request_preview()

    def _on_pick_solid_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self._solid_replacement_color = (c.red(), c.green(), c.blue())
            self._request_preview()

    def _on_browse_bg_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem de Fundo", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if f:
            self._custom_bg_image = Path(f)
            self._request_preview()

    def _request_preview(self):
        if not self._current_src_path:
            return
        self._preview_timer.start(150)

    def _do_update_preview(self):
        if not self._current_src_path or not self._current_src_path.is_file():
            return

        params = {
            "mode": self.cmb_mode.currentData(),
            "custom_color": self._custom_color,
            "tolerance": int(self.slider_tol.value()),
            "feather": int(self.slider_feather.value()),
            "bg_replacement_mode": self.cmb_bg_replace.currentData(),
            "bg_solid_color": self._solid_replacement_color,
            "bg_custom_image_path": self._custom_bg_image,
        }

        try:
            im = render_remove_bg_preview(self._current_src_path, params)
            import io
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue())
            self.canvas_res.set_pixmap(pix, auto_fit=False)
        except Exception as ex:
            pass

    def _on_save_result(self):
        if not self._current_src_path:
            QMessageBox.warning(self, "Aviso", "Carregue uma imagem primeiro.")
            return

        dest_str, _ = QFileDialog.getSaveFileName(self, "Salvar Imagem sem Fundo", "sem_fundo.png", "PNG (*.png);;WEBP (*.webp)")
        if not dest_str:
            return

        params = {
            "mode": self.cmb_mode.currentData(),
            "custom_color": self._custom_color,
            "tolerance": int(self.slider_tol.value()),
            "feather": int(self.slider_feather.value()),
            "bg_replacement_mode": self.cmb_bg_replace.currentData(),
            "bg_solid_color": self._solid_replacement_color,
            "bg_custom_image_path": self._custom_bg_image,
        }

        try:
            remove_image_background(
                input_path=self._current_src_path,
                output_path=Path(dest_str),
                **params
            )
            show_toast(self, f"Imagem salva em:\n{dest_str}")
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar: {ex}")
