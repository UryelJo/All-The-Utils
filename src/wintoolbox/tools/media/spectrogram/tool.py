"""
Interface gráfica do Gerador de Espectrograma e Forma de Onda (media.spectrogram).
Gera gráficos acústicos de alta fidelidade de arquivos de som e vídeo.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.media.spectrogram.logic import (
    generate_spectrogram,
    generate_waveform,
)


@register
class SpectrogramTool(Tool):
    id = "media.spectrogram"
    name = "Espectrograma e Forma de Onda de Áudio"
    description = "Gera espectrogramas de frequências sonoras e gráficos visuais de ondas acústicas via FFmpeg."
    category = "media"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção de arquivo
        top_box = QHBoxLayout()
        top_box.addWidget(QLabel("Arquivo de Áudio/Vídeo:"))
        self._edit_file = QLineEdit()
        self._edit_file.setPlaceholderText("Selecione um arquivo de áudio ou vídeo...")
        top_box.addWidget(self._edit_file)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_box.addWidget(btn_browse)
        layout.addLayout(top_box)

        # Configurações
        form = QFormLayout()
        self._combo_mode = QComboBox()
        self._combo_mode.addItem("Espectrograma de Frequências (Hz vs Tempo)", "SPECTRO")
        self._combo_mode.addItem("Forma de Onda de Amplitude (Waveform)", "WAVE")
        form.addRow("Tipo de Visualização:", self._combo_mode)

        self._combo_palette = QComboBox()
        self._combo_palette.addItem("Magma (Padrão Acústico)", "magma")
        self._combo_palette.addItem("Fire (Gradiente Fogo)", "fire")
        self._combo_palette.addItem("Intensity (Brilho / Calor)", "intensity")
        self._combo_palette.addItem("Rainbow (Arco-Íris)", "rainbow")
        form.addRow("Paleta de Cores:", self._combo_palette)

        layout.addLayout(form)

        # Botão Gerar
        self._btn_generate = QPushButton("Gerar Gráfico Acústico")
        self._btn_generate.clicked.connect(self._on_generate_click)
        layout.addWidget(self._btn_generate)

        # Área de Visualização da Imagem
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._lbl_preview = QLabel("O gráfico gerado aparecerá aqui.")
        self._lbl_preview.setAlignment(Qt.AlignCenter)
        self._lbl_preview.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; color: #888;")
        scroll.setWidget(self._lbl_preview)
        layout.addWidget(scroll, 1)

        # Botão Salvar
        self._btn_save = QPushButton("Salvar Imagem (PNG)...")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save_click)
        layout.addWidget(self._btn_save)

        self._current_image_path: Path | None = None
        return widget

    def _on_browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Arquivo",
            "",
            "Áudios e Vídeos (*.mp3 *.wav *.flac *.m4a *.ogg *.mp4 *.mkv *.webm);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_file.setText(path)

    def _on_generate_click(self) -> None:
        raw_path = self._edit_file.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo de áudio ou vídeo.")
            return

        src_path = Path(raw_path)
        if not src_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {src_path}")
            return

        mode = self._combo_mode.currentData()
        palette = self._combo_palette.currentData()

        # Cria PNG temporário para prévia
        import tempfile
        tmp_png = Path(tempfile.gettempdir()) / f"wintoolbox_spec_{src_path.stem}.png"

        self._btn_generate.setEnabled(False)
        self._lbl_preview.setText("Processando espectro acústico via FFmpeg...")

        def worker():
            if mode == "SPECTRO":
                return generate_spectrogram(src_path, tmp_png, color_map=palette)
            else:
                return generate_waveform(src_path, tmp_png)

        def on_done(res_png: Path):
            self._btn_generate.setEnabled(True)
            self._current_image_path = res_png
            pixmap = QPixmap(str(res_png))
            self._lbl_preview.setPixmap(pixmap.scaled(
                self._lbl_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))
            self._btn_save.setEnabled(True)

        def on_error(err: str):
            self._btn_generate.setEnabled(True)
            self._lbl_preview.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao gerar gráfico: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_save_click(self) -> None:
        if not self._current_image_path or not self._current_image_path.is_file():
            return

        out_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Gráfico Como",
            f"{self._current_image_path.stem}.png",
            "Imagens PNG (*.png)",
        )
        if out_str:
            import shutil
            shutil.copy2(self._current_image_path, Path(out_str))
            QMessageBox.information(None, "Sucesso", f"Imagem salva com sucesso em:\n{out_str}")
