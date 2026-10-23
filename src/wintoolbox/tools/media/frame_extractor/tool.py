"""
Ferramenta: Extrator de Frames de Vídeo em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.media.frame_extractor.logic import extract_video_frames


@register
class FrameExtractorTool(FileTool):
    id = "media.frame_extractor"
    name = "Extrator de Frames de Vídeo"
    category = "Áudio e Vídeo"
    description = "Extraia quadros ou gere mosaicos de miniaturas de vídeos a cada N segundos ou em tempo fixo"
    keywords = ["video", "frames", "quadros", "miniaturas", "screenshots", "ffmpeg", "mosaico", "lote"]
    accepts = [".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"]
    batch_kind = "per_file_multi"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Captura de Quadros")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Modo
        grid.addWidget(QLabel("Modo de extração:"), 0, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("A cada N segundos (Intervalo)", "interval")
        self.cmb_mode.addItem("Quadro em tempo específico (Timestamp)", "single")
        self.cmb_mode.addItem("Mosaico de miniaturas (Grade 3x3)", "tile")
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        grid.addWidget(self.cmb_mode, 0, 1)

        # Intervalo
        self.lbl_interval = QLabel("Intervalo (segundos):")
        grid.addWidget(self.lbl_interval, 1, 0)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 3600.0)
        self.spin_interval.setValue(5.0)
        self.spin_interval.setSuffix(" s")
        grid.addWidget(self.spin_interval, 1, 1)

        # Timestamp
        self.lbl_time = QLabel("Timestamp (HH:MM:SS):")
        self.lbl_time.setVisible(False)
        grid.addWidget(self.lbl_time, 2, 0)
        self.txt_time = QLineEdit("00:00:01")
        self.txt_time.setVisible(False)
        grid.addWidget(self.txt_time, 2, 1)

        # Formato da imagem
        grid.addWidget(QLabel("Formato dos frames:"), 3, 0)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(["PNG", "JPG"])
        grid.addWidget(self.cmb_format, 3, 1)

        layout.addLayout(grid)
        return panel

    def _on_mode_changed(self):
        mode = self.cmb_mode.currentData()
        self.lbl_interval.setVisible(mode == "interval")
        self.spin_interval.setVisible(mode == "interval")
        self.lbl_time.setVisible(mode == "single")
        self.txt_time.setVisible(mode == "single")

    def get_params(self) -> Dict[str, Any]:
        return {
            "mode": self.cmb_mode.currentData(),
            "interval_sec": self.spin_interval.value(),
            "timestamp": self.txt_time.text().strip(),
            "format": self.cmb_format.currentText().lower(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = params.get("format", "png").lower()
        return f".{fmt}"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext
    ) -> ItemResult:
        try:
            # Em per_file_multi, dst pode ser a pasta ou arquivo alvo
            out_dir = dst.parent if dst.suffix else dst
            mode = params.get("mode", "interval")
            sec = params.get("interval_sec", 5.0)
            t_stamp = params.get("timestamp", "00:00:01")
            fmt = params.get("format", "png")

            frames = extract_video_frames(
                src,
                out_dir,
                mode=mode,
                interval_sec=sec,
                timestamp=t_stamp,
                img_format=fmt,
                prefix=src.stem
            )

            count = len(frames)
            return ItemResult(
                success=True,
                output_path=out_dir,
                message=f"{count} quadros extraídos para {out_dir.name}"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                error=f"Falha ao extrair quadros de {src.name}: {e}"
            )
