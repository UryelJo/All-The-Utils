"""
Ferramenta: Conversor de Vídeo e Áudio em Lote.
Implementação completa herdando de FileTool com suporte a formatos populares,
extração de áudio, compressão por meta de MB e conversão para GIF animado.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.media.convert.logic import (
    ALL_OUTPUT_FORMATS, AUDIO_FORMATS, convert_media_file
)


@register
class MediaConvertTool(FileTool):
    id = "media.convert"
    name = "Conversor de Vídeo e Áudio"
    category = "Áudio e Vídeo"
    description = "Converta vídeos e músicas em lote, extraia áudio de vídeos, gere GIFs animados ou comprima para meta de tamanho"
    keywords = ["video", "audio", "conversor", "mp4", "mp3", "mkv", "gif", "comprimir", "extrair audio", "ffmpeg", "lote"]
    accepts = [
        ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"
    ]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Conversão e Otimização")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Formato de saída
        grid.addWidget(QLabel("Formato de saída:"), 0, 0)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems([fmt.upper() for fmt in ALL_OUTPUT_FORMATS])
        self.cmb_format.setCurrentText("MP4")
        self.cmb_format.currentTextChanged.connect(self._on_format_changed)
        grid.addWidget(self.cmb_format, 0, 1)

        # Extrair áudio apenas
        self.chk_extract_audio = QCheckBox("Extrair apenas a faixa de áudio (ignorar vídeo)")
        self.chk_extract_audio.toggled.connect(self._on_audio_toggled)
        grid.addWidget(self.chk_extract_audio, 1, 0, 1, 2)

        # Compressão por meta de MB
        grid.addWidget(QLabel("Meta de tamanho (MB) [opcional]:"), 2, 0)
        self.spin_target_mb = QDoubleSpinBox()
        self.spin_target_mb.setRange(0.0, 10000.0)
        self.spin_target_mb.setValue(0.0)
        self.spin_target_mb.setSpecialValueText("Desativado (qualidade padrão)")
        self.spin_target_mb.setSuffix(" MB")
        grid.addWidget(self.spin_target_mb, 2, 1)

        # Opções de GIF
        self.lbl_gif_fps = QLabel("FPS do GIF:")
        self.lbl_gif_fps.setVisible(False)
        grid.addWidget(self.lbl_gif_fps, 3, 0)

        self.spin_gif_fps = QSpinBox()
        self.spin_gif_fps.setRange(1, 60)
        self.spin_gif_fps.setValue(15)
        self.spin_gif_fps.setVisible(False)
        grid.addWidget(self.spin_gif_fps, 3, 1)

        layout.addLayout(grid)
        return panel

    def _on_format_changed(self, text: str):
        is_gif = (text.upper() == "GIF")
        self.lbl_gif_fps.setVisible(is_gif)
        self.spin_gif_fps.setVisible(is_gif)

    def _on_audio_toggled(self, checked: bool):
        if checked:
            fmt = self.cmb_format.currentText().lower()
            if fmt not in AUDIO_FORMATS:
                self.cmb_format.setCurrentText("MP3")

    def get_params(self) -> Dict[str, Any]:
        return {
            "format": self.cmb_format.currentText().lower(),
            "extract_audio": self.chk_extract_audio.isChecked(),
            "target_size_mb": self.spin_target_mb.value(),
            "gif_fps": self.spin_gif_fps.value(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = params.get("format", "mp4").lower()
        return f".{fmt}"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext
    ) -> ItemResult:
        try:
            target_fmt = params.get("format", "mp4").lower()
            audio_only = params.get("extract_audio", False)
            target_mb = params.get("target_size_mb", 0.0)
            fps = params.get("gif_fps", 15)

            convert_media_file(
                src,
                dst,
                target_format=target_fmt,
                extract_audio_only=audio_only,
                target_size_mb=target_mb if target_mb > 0 else None,
                gif_fps=fps
            )

            sz_mb = dst.stat().st_size / (1024 * 1024)
            return ItemResult(
                success=True,
                output_path=dst,
                message=f"Convertido com sucesso ({sz_mb:.2f} MB)"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                error=f"Falha ao converter {src.name}: {e}"
            )
