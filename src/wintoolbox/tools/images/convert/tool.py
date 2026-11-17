"""
Ferramenta: Conversor Universal de Imagens em Lote (com suporte a vetores SVG, Ícones .ICO e Favicons).
Implementação completa herdando de FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
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
from wintoolbox.tools.images.favicon.logic import (
    DEFAULT_ICO_SIZES,
    generate_multi_size_ico,
    generate_web_favicon_package,
)
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.convert.ui")


@register
class ImageConverterTool(FileTool):
    id = "images.convert"
    name = "Conversor de Imagens"
    category = "Imagens"
    description = (
        "Conversão universal em lote entre formatos modernos, vetores SVG, ícones .ICO e favicons para web"
    )
    keywords = [
        "imagem", "foto", "converter", "heic", "heif", "hif", "iphone", "apple",
        "avif", "webp", "jpeg", "jpg", "png", "ico", "icns", "qoi", "psd", "tga",
        "dds", "jp2", "tiff", "gif", "pdf", "svg", "favicon", "lote", "pasta"
    ]
    accepts = list(SUPPORTED_IMAGE_INPUTS)
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        tabs = QTabWidget(parent)
        tabs.setProperty("class", "card")

        # Aba 1: Opções de Conversão em Lote
        tab_convert = QWidget()
        layout = QVBoxLayout(tab_convert)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

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
        self.slider_quality = SliderSpinControl("Qualidade:", 10, 100, 90, suffix="%")
        self.slider_quality.valueChanged.connect(lambda _: self._sync_controls_state())
        qual_row.addWidget(self.slider_quality)

        self.chk_lossless = QCheckBox("Sem perdas")
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
        tabs.addTab(tab_convert, "Conversão em Lote")

        # Aba 2: Ícones .ICO & Favicons Web
        tab_ico = self._build_favicon_tab()
        tabs.addTab(tab_ico, "Ícones .ICO & Favicons Web")

        self._active_file: Optional[Path] = None
        self._sync_controls_state()
        return tabs

    def _build_favicon_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_info = QLabel("Gere arquivos .ico com múltiplas resoluções ou pacotes prontos para sites.")
        lbl_info.setStyleSheet("color: #8F96A0; font-size: 12px;")
        layout.addWidget(lbl_info)

        lbl_sizes = QLabel("Tamanhos embutidos no arquivo .ico:")
        lbl_sizes.setStyleSheet("font-weight: 500; font-size: 12px;")
        layout.addWidget(lbl_sizes)

        grid_sizes = QGridLayout()
        grid_sizes.setHorizontalSpacing(12)
        grid_sizes.setVerticalSpacing(4)
        self.chk_ico_sizes = {}
        for idx, sz in enumerate(DEFAULT_ICO_SIZES):
            chk = QCheckBox(f"{sz}×{sz} px")
            chk.setChecked(True)
            self.chk_ico_sizes[sz] = chk
            grid_sizes.addWidget(chk, idx // 4, idx % 4)
        layout.addLayout(grid_sizes)

        # Diretório opcional de saída
        row_dir = QHBoxLayout()
        row_dir.setSpacing(8)
        row_dir.addWidget(QLabel("Diretório de saída (opcional):"))
        self.txt_ico_out_dir = QLineEdit()
        self.txt_ico_out_dir.setPlaceholderText("Mesma pasta da imagem de origem")
        row_dir.addWidget(self.txt_ico_out_dir, stretch=1)

        btn_browse_out = QPushButton("Procurar...")
        btn_browse_out.clicked.connect(self._on_browse_ico_out)
        row_dir.addWidget(btn_browse_out)
        layout.addLayout(row_dir)

        # Botões de ação direta
        row_actions = QHBoxLayout()
        row_actions.setSpacing(10)

        btn_ico = QPushButton("Gerar .ICO da Imagem Selecionada")
        btn_ico.setProperty("class", "primary")
        btn_ico.clicked.connect(self._generate_ico_from_active)
        row_actions.addWidget(btn_ico)

        btn_web = QPushButton("Gerar Pacote Favicon Web Completo...")
        btn_web.clicked.connect(self._generate_web_package)
        row_actions.addWidget(btn_web)

        row_actions.addStretch()
        layout.addLayout(row_actions)

        return w

    def on_active_file_changed(self, path: Path) -> None:
        self._active_file = path

    def _on_browse_ico_out(self) -> None:
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Diretório de Saída")
        if folder:
            self.txt_ico_out_dir.setText(folder)

    def _generate_ico_from_active(self) -> None:
        if not self._active_file or not self._active_file.is_file():
            QMessageBox.warning(None, "Aviso", "Por favor, adicione e selecione uma imagem na lista acima primeiro.")
            return

        sizes = [sz for sz, chk in self.chk_ico_sizes.items() if chk.isChecked()]
        if not sizes:
            QMessageBox.warning(None, "Aviso", "Selecione pelo menos um tamanho para o .ico.")
            return

        out_dir = self.txt_ico_out_dir.text().strip()
        if out_dir and Path(out_dir).is_dir():
            target_ico = Path(out_dir) / f"{self._active_file.stem}.ico"
        else:
            target_ico = self._active_file.with_suffix(".ico")

        try:
            generate_multi_size_ico(self._active_file, target_ico, sizes)
            QMessageBox.information(None, "Sucesso", f"Arquivo .ICO criado com sucesso:\n{target_ico}")
        except Exception as ex:
            QMessageBox.critical(None, "Erro", f"Falha ao gerar .ico: {ex}")

    def _generate_web_package(self) -> None:
        if not self._active_file or not self._active_file.is_file():
            QMessageBox.warning(None, "Aviso", "Selecione uma imagem na lista acima primeiro.")
            return

        out_dir = QFileDialog.getExistingDirectory(None, "Pasta de Destino para o Pacote Web")
        if not out_dir:
            return

        try:
            generate_web_favicon_package(
                self._active_file,
                Path(out_dir),
                app_name="Web App",
                theme_color="#0078D4"
            )
            QMessageBox.information(None, "Sucesso", f"Pacote Web gerado com sucesso em:\n{out_dir}")
        except Exception as ex:
            QMessageBox.critical(None, "Erro", f"Falha ao gerar pacote web: {ex}")

    def _sync_controls_state(self) -> None:
        fmt = self.cmb_format.currentText().upper()
        pillow_fmt = PILLOW_FORMAT_MAP.get(fmt, fmt)

        can_toggle_lossless = fmt in LOSSLESS_TOGGLE_FORMATS
        self.chk_lossless.setEnabled(can_toggle_lossless)
        is_lossless_active = can_toggle_lossless and self.chk_lossless.isChecked()

        is_lossy_slider_active = (fmt in LOSSY_CAPABLE_FORMATS) and not is_lossless_active
        self.slider_quality.setEnabled(is_lossy_slider_active)

        can_subsample = (fmt in SUBSAMPLING_CAPABLE_FORMATS) and not is_lossless_active
        self.cmb_subsampling.setEnabled(can_subsample)

        self.cmb_bg_color.setEnabled(pillow_fmt in NO_ALPHA_FORMATS)

    def get_options(self) -> Dict[str, Any]:
        fmt = self.cmb_format.currentText().upper()
        lossless = (fmt in LOSSLESS_TOGGLE_FORMATS) and self.chk_lossless.isChecked()
        return {
            "format": fmt,
            "quality": int(self.slider_quality.value()),
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
