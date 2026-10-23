"""
Ferramenta: Gravador de Tela do Windows.
Captura instantânea da área de trabalho com controle de tempo e exportação para MP4.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.media.recorder.logic import ScreenRecorder


@register
class MediaRecorderTool(Tool):
    id = "media.recorder"
    name = "Gravador de Tela"
    category = "Áudio e Vídeo"
    description = "Grave a tela do Windows em alta definição (MP4) com captura nativa via ffmpeg"
    keywords = ["gravador", "tela", "record", "screen", "captura", "gdigrab", "desktop", "mp4"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Gravador de Tela do Windows")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        self.recorder = ScreenRecorder()

        # Configurações de Gravação
        grp_opts = QGroupBox("Configurações de Captura")
        grid = QGridLayout(grp_opts)

        grid.addWidget(QLabel("Taxa de quadros (FPS):"), 0, 0)
        self.cmb_fps = QComboBox()
        self.cmb_fps.addItem("30 FPS (Padrão)", 30)
        self.cmb_fps.addItem("60 FPS (Fluidez Alta)", 60)
        self.cmb_fps.addItem("15 FPS (Arquivo Leve)", 15)
        grid.addWidget(self.cmb_fps, 0, 1)

        grid.addWidget(QLabel("Arquivo de saída:"), 1, 0)
        self.txt_output_path = QLineEdit()
        default_dir = Path.home() / "Videos"
        if not default_dir.exists():
            default_dir = Path.home() / "Desktop"
        default_name = f"gravacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        self.txt_output_path.setText(str(default_dir / default_name))
        grid.addWidget(self.txt_output_path, 1, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_output)
        grid.addWidget(btn_browse, 1, 2)

        main_layout.addWidget(grp_opts)

        # Painel Central de Status e Tempo
        timer_box = QFrame()
        timer_box.setProperty("class", "card")
        timer_layout = QVBoxLayout(timer_box)
        timer_layout.setAlignment(Qt.AlignCenter)

        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setStyleSheet("font-size: 32px; font-weight: 700; color: #0078d4;")
        timer_layout.addWidget(self.lbl_timer, alignment=Qt.AlignCenter)

        self.lbl_status = QLabel("Pronto para iniciar gravação.")
        self.lbl_status.setStyleSheet("color: gray; font-size: 12px;")
        timer_layout.addWidget(self.lbl_status, alignment=Qt.AlignCenter)

        main_layout.addWidget(timer_box)

        # Botões de Ação
        act_box = QHBoxLayout()
        act_box.addStretch()

        self.btn_start = QPushButton("Iniciar Gravação")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self._on_start_recording)
        act_box.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Parar e Salvar")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.clicked.connect(self._on_stop_recording)
        act_box.addWidget(self.btn_stop)

        act_box.addStretch()
        main_layout.addLayout(act_box)
        main_layout.addStretch()

        # QTimer para atualizar cronômetro
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_timer_tick)

        return container

    def _on_browse_output(self):
        file, _ = QFileDialog.getSaveFileName(None, "Salvar Gravação", "gravacao_tela.mp4", "Vídeo MP4 (*.mp4)")
        if file:
            self.txt_output_path.setText(file)

    def _on_start_recording(self):
        out_p = self.txt_output_path.text().strip()
        if not out_p:
            QMessageBox.warning(None, "Aviso", "Informe o caminho do arquivo de destino.")
            return

        fps = self.cmb_fps.currentData()
        try:
            self.recorder.start_recording(Path(out_p), fps=fps)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.lbl_status.setText("Gravando a tela do Windows...")
            self.timer.start()
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Não foi possível iniciar gravação: {e}")

    def _on_stop_recording(self):
        self.timer.stop()
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Finalizando arquivo de vídeo...")

        try:
            saved_file = self.recorder.stop_recording()
            self.btn_start.setEnabled(True)
            self.lbl_status.setText(f"Gravação concluída e salva com sucesso.")
            sz_mb = saved_file.stat().st_size / (1024 * 1024)
            QMessageBox.information(
                None,
                "Gravação Concluída",
                f"Gravação de tela salva com sucesso!\n\nArquivo: {saved_file}\nTamanho: {sz_mb:.2f} MB"
            )
        except Exception as e:
            self.btn_start.setEnabled(True)
            self.lbl_status.setText(f"Erro: {e}")
            QMessageBox.critical(None, "Erro", f"Falha ao finalizar gravação: {e}")

    def _on_timer_tick(self):
        secs = int(self.recorder.get_elapsed_seconds())
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        self.lbl_timer.setText(f"{h:02d}:{m:02d}:{s:02d}")
