"""
Interface de usuário para a ferramenta Alterar Velocidade de Mídia.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.media.speed_changer.logic import change_media_speed


@register
class SpeedChangerTool(FileTool):
    """Ferramenta para acelerar ou desacelerar áudio e vídeo."""

    id = "media.speed_changer"
    name = "Alterar Velocidade de Mídia"
    description = "Acelera ou desacelera áudio e vídeo mantendo ou alterando o tom da voz."
    category = "media"
    extensions = [
        ".mp4", ".mkv", ".mov", ".avi", ".webm",
        ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"
    ]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Controle de Velocidade
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Velocidade:")
        
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.25, 4.0)
        self.spin_speed.setSingleStep(0.25)
        self.spin_speed.setValue(1.5)
        self.spin_speed.setSuffix("x")

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(25, 400)
        self.slider_speed.setValue(150)
        self.slider_speed.setSingleStep(25)

        # Sincronização entre Slider e SpinBox
        self.spin_speed.valueChanged.connect(
            lambda val: self.slider_speed.setValue(int(val * 100))
        )
        self.slider_speed.valueChanged.connect(
            lambda val: self.spin_speed.setValue(val / 100.0)
        )

        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.slider_speed)
        speed_layout.addWidget(self.spin_speed)
        layout.addLayout(speed_layout)

        # Checkbox Preservar Tom
        self.check_pitch = QCheckBox("Preservar tom original da voz (Pitch Correction)")
        self.check_pitch.setChecked(True)
        self.check_pitch.setToolTip(
            "Se marcado, a velocidade é alterada sem deixar a voz 'fina' (efeito esquilo) "
            "ou excessivamente grave."
        )
        layout.addWidget(self.check_pitch)

        return widget

    def get_options(self) -> Dict[str, Any]:
        return {
            "speed": self.spin_speed.value(),
            "preserve_pitch": self.check_pitch.isChecked(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        speed = options.get("speed", 1.5)
        preserve_pitch = options.get("preserve_pitch", True)

        speed_str = f"{speed:.2f}".replace(".", "_")
        pitch_suffix = "" if preserve_pitch else "_pitchmod"
        out_name = f"{input_path.stem}_{speed_str}x{pitch_suffix}{input_path.suffix}"
        output_path = output_dir / out_name

        return change_media_speed(
            input_path=input_path,
            output_path=output_path,
            speed=speed,
            preserve_pitch=preserve_pitch
        )
