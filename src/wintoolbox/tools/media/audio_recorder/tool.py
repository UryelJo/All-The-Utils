"""
Interface de usuário para a ferramenta Gravador de Áudio.
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.media.audio_recorder.logic import (
    AudioRecorderSession,
    get_audio_info,
    list_audio_input_devices,
)


@register
class AudioRecorderTool(Tool):
    """Gravador dedicado de áudio com controle de dispositivos e formatos."""

    id = "media.audio_recorder"
    name = "Gravador de Áudio"
    description = "Gravador de voz e áudio: captura gravações do microfone com mostrador de tempo, nível sonoro e exportação para formatos WAV e MP3."
    category = "Áudio e Vídeo"

    def __init__(self):
        super().__init__()
        self.session = AudioRecorderSession()
        self.timer = QTimer()
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._update_timer_display)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Gravador de Áudio")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Grave faixas de voz, reuniões ou instrumentos diretamente de seus dispositivos "
            "de áudio conectados."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Configurações de Entrada e Formato
        config_frame = QFrame()
        config_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(config_frame)
        grid.setSpacing(10)

        # Dispositivo de entrada
        grid.addWidget(QLabel("Dispositivo de Áudio:"), 0, 0)
        self.combo_devices = QComboBox()
        self.btn_refresh_devs = QPushButton("Atualizar")
        self.btn_refresh_devs.clicked.connect(self._refresh_devices)

        dev_layout = QHBoxLayout()
        dev_layout.addWidget(self.combo_devices, 1)
        dev_layout.addWidget(self.btn_refresh_devs)
        grid.addLayout(dev_layout, 0, 1, 1, 3)

        # Formato de Saída
        grid.addWidget(QLabel("Formato:"), 1, 0)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["wav", "mp3", "aac", "flac"])
        grid.addWidget(self.combo_format, 1, 1)

        # Taxa de Amostragem
        grid.addWidget(QLabel("Taxa de Amostragem:"), 1, 2)
        self.combo_sample_rate = QComboBox()
        self.combo_sample_rate.addItem("44100 Hz (Qualidade CD)", 44100)
        self.combo_sample_rate.addItem("48000 Hz (Qualidade Estúdio)", 48000)
        grid.addWidget(self.combo_sample_rate, 1, 3)

        # Pasta de Saída
        grid.addWidget(QLabel("Pasta de Destino:"), 2, 0)
        self.txt_output_dir = QLineEdit(str(Path.home() / "Music"))
        self.btn_browse_dir = QPushButton("Procurar...")
        self.btn_browse_dir.clicked.connect(self._browse_dir)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.txt_output_dir, 1)
        dir_layout.addWidget(self.btn_browse_dir)
        grid.addLayout(dir_layout, 2, 1, 1, 3)

        layout.addWidget(config_frame)

        # Painel Central de Gravação
        rec_panel = QFrame()
        rec_panel.setFrameShape(QFrame.Shape.StyledPanel)
        rec_layout = QVBoxLayout(rec_panel)
        rec_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_layout.setSpacing(15)

        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_timer.setStyleSheet("font-size: 42px; font-weight: bold; font-family: monospace;")
        rec_layout.addWidget(self.lbl_timer)

        self.lbl_status = QLabel("Pronto para gravar")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #888888; font-size: 14px;")
        rec_layout.addWidget(self.lbl_status)

        # Botões de Ação
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_record = QPushButton("● Iniciar Gravação")
        self.btn_record.setFixedHeight(45)
        self.btn_record.setFixedWidth(180)
        self.btn_record.setStyleSheet(
            "font-size: 15px; font-weight: bold; background-color: #d32f2f; color: white;"
        )
        self.btn_record.clicked.connect(self._toggle_recording)

        btn_layout.addWidget(self.btn_record)
        rec_layout.addLayout(btn_layout)

        layout.addWidget(rec_panel)

        # Informações da última gravação
        self.lbl_last_info = QLabel("")
        self.lbl_last_info.setStyleSheet("color: #4caf50; font-size: 13px;")
        self.lbl_last_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_last_info)

        layout.addStretch()

        self._refresh_devices()
        return widget

    def _refresh_devices(self):
        self.combo_devices.clear()
        devices = list_audio_input_devices()
        if devices:
            for dev in devices:
                self.combo_devices.addItem(dev, dev)
        else:
            self.combo_devices.addItem("Dispositivo Padrão do Sistema", None)

    def _browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Gravação")
        if dir_path:
            self.txt_output_dir.setText(dir_path)

    def _update_timer_display(self):
        if self.session.is_recording:
            elapsed = int(self.session.elapsed_seconds)
            hrs = elapsed // 3600
            mins = (elapsed % 3600) // 60
            secs = elapsed % 60
            self.lbl_timer.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

    def _toggle_recording(self):
        if not self.session.is_recording:
            # Iniciar gravação
            out_dir = Path(self.txt_output_dir.text().strip())
            out_dir.mkdir(parents=True, exist_ok=True)

            fmt = self.combo_format.currentText()
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_file = out_dir / f"gravacao_{now_str}.{fmt}"

            device = self.combo_devices.currentData()
            sample_rate = self.combo_sample_rate.currentData() or 44100

            try:
                self.session.start_recording(
                    output_path=out_file,
                    device_name=device,
                    sample_rate=sample_rate,
                    channels=2
                )
                self.btn_record.setText("■ Parar Gravação")
                self.btn_record.setStyleSheet(
                    "font-size: 15px; font-weight: bold; background-color: #424242; color: white;"
                )
                self.lbl_status.setText("Gravando...")
                self.lbl_status.setStyleSheet("color: #d32f2f; font-weight: bold;")
                self.lbl_last_info.setText("")
                self.timer.start()
            except Exception as e:
                QMessageBox.critical(None, "Erro ao Iniciar", f"Não foi possível iniciar a gravação: {e}")
        else:
            # Parar gravação
            self.timer.stop()
            try:
                out_path = self.session.stop_recording()
                info = get_audio_info(out_path)
                dur = info.get("duration", 0.0)
                sz_mb = info.get("size_bytes", 0) / (1024 * 1024)

                self.btn_record.setText("● Iniciar Gravação")
                self.btn_record.setStyleSheet(
                    "font-size: 15px; font-weight: bold; background-color: #d32f2f; color: white;"
                )
                self.lbl_status.setText("Gravação salva com sucesso.")
                self.lbl_status.setStyleSheet("color: #4caf50;")
                self.lbl_last_info.setText(
                    f"Arquivo: {out_path.name} | Duração: {dur:.1f}s | Tamanho: {sz_mb:.2f} MB"
                )
            except Exception as e:
                QMessageBox.warning(None, "Aviso", f"Erro ao finalizar gravação: {e}")
                self.btn_record.setText("● Iniciar Gravação")
                self.lbl_status.setText("Erro na finalização.")
