"""
Interface de usuário para a ferramenta Marca d'Água em Vídeo.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.media.video_watermark.logic import apply_video_watermark


@register
class VideoWatermarkTool(FileTool):
    """Ferramenta para inserção de marca d'água de texto ou imagem em vídeos."""

    id = "media.video_watermark"
    name = "Marca d'Água em Vídeo"
    description = "Insere logotipos PNG transparentes ou textos estilizados sobre vídeos em lote."
    category = "media"
    extensions = [".mp4", ".mkv", ".mov", ".avi", ".webm"]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Escolha de Tipo (Texto / Imagem)
        type_layout = QHBoxLayout()
        self.radio_text = QRadioButton("Texto")
        self.radio_image = QRadioButton("Imagem (PNG com transparência)")
        self.radio_text.setChecked(True)

        self.btn_group = QButtonGroup(widget)
        self.btn_group.addButton(self.radio_text)
        self.btn_group.addButton(self.radio_image)

        type_layout.addWidget(QLabel("Tipo:"))
        type_layout.addWidget(self.radio_text)
        type_layout.addWidget(self.radio_image)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # Configurações de Texto
        self.text_container = QWidget()
        text_layout = QHBoxLayout(self.text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.txt_content = QLineEdit("Confidencial")
        self.txt_content.setPlaceholderText("Digite o texto da marca d'água")

        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 120)
        self.spin_font_size.setValue(32)
        self.spin_font_size.setSuffix(" px")

        text_layout.addWidget(QLabel("Texto:"))
        text_layout.addWidget(self.txt_content, 2)
        text_layout.addWidget(QLabel("Tamanho:"))
        text_layout.addWidget(self.spin_font_size)
        layout.addWidget(self.text_container)

        # Configurações de Imagem
        self.image_container = QWidget()
        image_layout = QHBoxLayout(self.image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self.txt_image_path = QLineEdit()
        self.txt_image_path.setPlaceholderText("Selecione um arquivo de imagem (PNG)...")
        self.btn_browse_img = QPushButton("Procurar...")
        self.btn_browse_img.clicked.connect(self._browse_image)

        image_layout.addWidget(QLabel("Imagem:"))
        image_layout.addWidget(self.txt_image_path, 2)
        image_layout.addWidget(self.btn_browse_img)
        self.image_container.setVisible(False)
        layout.addWidget(self.image_container)

        # Conectar alternância de tipo
        self.radio_text.toggled.connect(self._toggle_type)

        # Configurações de Posição e Opacidade
        grid = QGridLayout()

        grid.addWidget(QLabel("Posição:"), 0, 0)
        self.combo_position = QComboBox()
        self.combo_position.addItem("Canto Inferior Direito", "bottom_right")
        self.combo_position.addItem("Canto Inferior Esquerdo", "bottom_left")
        self.combo_position.addItem("Canto Superior Direito", "top_right")
        self.combo_position.addItem("Canto Superior Esquerdo", "top_left")
        self.combo_position.addItem("Centro", "center")
        self.combo_position.addItem("Centro Superior", "top_center")
        self.combo_position.addItem("Centro Inferior", "bottom_center")
        grid.addWidget(self.combo_position, 0, 1)

        grid.addWidget(QLabel("Opacidade:"), 0, 2)
        opacity_layout = QHBoxLayout()
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(80)

        self.lbl_opacity = QLabel("80%")
        self.slider_opacity.valueChanged.connect(
            lambda v: self.lbl_opacity.setText(f"{v}%")
        )
        opacity_layout.addWidget(self.slider_opacity)
        opacity_layout.addWidget(self.lbl_opacity)
        grid.addLayout(opacity_layout, 0, 3)

        layout.addLayout(grid)
        return widget

    def _toggle_type(self, is_text: bool):
        self.text_container.setVisible(is_text)
        self.image_container.setVisible(not is_text)

    def _browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Imagem de Marca d'Água",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.txt_image_path.setText(file_path)

    def get_options(self) -> Dict[str, Any]:
        is_text = self.radio_text.isChecked()
        return {
            "watermark_type": "text" if is_text else "image",
            "text": self.txt_content.text(),
            "image_path": self.txt_image_path.text().strip() or None,
            "position": self.combo_position.currentData(),
            "opacity": self.slider_opacity.value() / 100.0,
            "font_size": self.spin_font_size.value(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        out_name = f"{input_path.stem}_watermarked{input_path.suffix}"
        output_path = output_dir / out_name

        wm_type = options.get("watermark_type", "text")
        text = options.get("text", "")
        img_raw = options.get("image_path")
        image_path = Path(img_raw) if img_raw else None
        position = options.get("position", "bottom_right")
        opacity = options.get("opacity", 0.8)
        font_size = options.get("font_size", 32)

        return apply_video_watermark(
            input_path=input_path,
            output_path=output_path,
            watermark_type=wm_type,
            text=text,
            image_path=image_path,
            position=position,
            opacity=opacity,
            font_size=font_size
        )
