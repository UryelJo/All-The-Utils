"""
Interface de usuário para a ferramenta Divisor de CUE Sheet.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.media.cue_splitter.logic import (
    CueSheet,
    find_audio_file,
    format_seconds_to_time,
    parse_cue_file,
    split_cue_audio,
)


@register
class CueSplitterTool(Tool):
    """Ferramenta para fatiar arquivos contínuos de álbum via CUE Sheet."""

    id = "media.cue_splitter"
    name = "Divisor de CUE Sheet"
    description = "Separador de áudio por arquivo CUE: divide um arquivo contínuo de áudio (FLAC, WAV, APE) em faixas individuais nomeadas conforme a folha CUE."
    category = "Áudio e Vídeo"

    def __init__(self):
        super().__init__()
        self.current_cue_sheet: Optional[CueSheet] = None

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Divisor de CUE Sheet")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Extraia faixas individuais nomeadas e com tags de metadados a partir de "
            "uma folha de CUE e seu arquivo de áudio mestre."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Painel de Seleção de Arquivos
        file_frame = QFrame()
        file_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid_files = QGridLayout(file_frame)
        grid_files.setSpacing(10)

        grid_files.addWidget(QLabel("Arquivo .CUE:"), 0, 0)
        self.txt_cue_path = QLineEdit()
        self.txt_cue_path.setPlaceholderText("Selecione o arquivo .cue...")
        self.btn_browse_cue = QPushButton("Procurar CUE...")
        self.btn_browse_cue.clicked.connect(self._browse_cue)
        grid_files.addWidget(self.txt_cue_path, 0, 1)
        grid_files.addWidget(self.btn_browse_cue, 0, 2)

        grid_files.addWidget(QLabel("Arquivo de Áudio:"), 1, 0)
        self.txt_audio_path = QLineEdit()
        self.txt_audio_path.setPlaceholderText("Detectado automaticamente ao abrir o CUE...")
        self.btn_browse_audio = QPushButton("Procurar Áudio...")
        self.btn_browse_audio.clicked.connect(self._browse_audio)
        grid_files.addWidget(self.txt_audio_path, 1, 1)
        grid_files.addWidget(self.btn_browse_audio, 1, 2)

        layout.addWidget(file_frame)

        # Informações do Álbum
        self.lbl_album_info = QLabel("Nenhum arquivo CUE carregado.")
        self.lbl_album_info.setStyleSheet("font-weight: bold; color: #2196f3;")
        layout.addWidget(self.lbl_album_info)

        # Tabela de Faixas
        self.table_tracks = QTableWidget()
        self.table_tracks.setColumnCount(4)
        self.table_tracks.setHorizontalHeaderLabels(["#", "Título da Faixa", "Artista", "Início"])
        self.table_tracks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_tracks.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_tracks, 1)

        # Opções de Exportação
        opt_frame = QFrame()
        opt_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid_opt = QGridLayout(opt_frame)
        grid_opt.setSpacing(10)

        grid_opt.addWidget(QLabel("Formato de Saída:"), 0, 0)
        self.combo_format = QComboBox()
        self.combo_format.addItem("Manter Original (Sem Perdas)", "keep")
        self.combo_format.addItem("FLAC (Livre de Perdas)", "flac")
        self.combo_format.addItem("MP3 (320 kbps VBR 0)", "mp3")
        self.combo_format.addItem("WAV (PCM Linear)", "wav")
        grid_opt.addWidget(self.combo_format, 0, 1)

        grid_opt.addWidget(QLabel("Padrão de Nome:"), 0, 2)
        self.txt_pattern = QLineEdit("{track:02d} - {title}")
        grid_opt.addWidget(self.txt_pattern, 0, 3)

        grid_opt.addWidget(QLabel("Pasta de Destino:"), 1, 0)
        self.txt_out_dir = QLineEdit()
        self.txt_out_dir.setPlaceholderText("Mesma pasta do arquivo CUE (padrão)...")
        self.btn_browse_out = QPushButton("Procurar Pasta...")
        self.btn_browse_out.clicked.connect(self._browse_out_dir)
        grid_opt.addWidget(self.txt_out_dir, 1, 1, 1, 2)
        grid_opt.addWidget(self.btn_browse_out, 1, 3)

        layout.addWidget(opt_frame)

        # Botão de Ação
        self.btn_split = QPushButton("Fatiar e Extrair Faixas")
        self.btn_split.setFixedHeight(40)
        self.btn_split.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_split.clicked.connect(self._split_audio)
        layout.addWidget(self.btn_split)

        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        return widget

    def _browse_cue(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Selecionar Arquivo CUE", "", "CUE Sheets (*.cue)"
        )
        if file_path:
            self.txt_cue_path.setText(file_path)
            self._load_cue(Path(file_path))

    def _browse_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Selecionar Arquivo de Áudio Mestre", "",
            "Áudio (*.flac *.wav *.ape *.mp3 *.m4a *.ogg *.wv)"
        )
        if file_path:
            self.txt_audio_path.setText(file_path)

    def _browse_out_dir(self):
        dir_path = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Destino")
        if dir_path:
            self.txt_out_dir.setText(dir_path)

    def _load_cue(self, cue_path: Path):
        try:
            sheet = parse_cue_file(cue_path)
            self.current_cue_sheet = sheet

            # Atualiza info do álbum
            self.lbl_album_info.setText(
                f"Álbum: {sheet.album_title} | Artista: {sheet.album_performer} | "
                f"Total de Faixas: {len(sheet.tracks)}"
            )

            # Localiza áudio
            audio = find_audio_file(cue_path, sheet.referenced_file)
            if audio:
                self.txt_audio_path.setText(str(audio))
            else:
                self.txt_audio_path.clear()

            # Preenche tabela
            self.table_tracks.setRowCount(len(sheet.tracks))
            for row, trk in enumerate(sheet.tracks):
                item_num = QTableWidgetItem(f"{trk.number:02d}")
                item_title = QTableWidgetItem(trk.title)
                item_artist = QTableWidgetItem(trk.performer)
                item_time = QTableWidgetItem(format_seconds_to_time(trk.start_seconds))

                self.table_tracks.setItem(row, 0, item_num)
                self.table_tracks.setItem(row, 1, item_title)
                self.table_tracks.setItem(row, 2, item_artist)
                self.table_tracks.setItem(row, 3, item_time)

            self.lbl_status.setText(f"CUE carregado com {len(sheet.tracks)} faixas.")
            self.lbl_status.setStyleSheet("color: #4caf50;")
        except Exception as e:
            QMessageBox.critical(None, "Erro ao Abrir CUE", f"Falha ao processar arquivo CUE: {e}")
            self.lbl_status.setText("Erro ao carregar CUE.")
            self.lbl_status.setStyleSheet("color: #f44336;")

    def _split_audio(self):
        cue_raw = self.txt_cue_path.text().strip()
        if not cue_raw:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo .cue antes de fatiar.")
            return

        cue_path = Path(cue_raw)
        audio_raw = self.txt_audio_path.text().strip()
        audio_path = Path(audio_raw) if audio_raw else None

        out_raw = self.txt_out_dir.text().strip()
        out_dir = Path(out_raw) if out_raw else None

        pattern = self.txt_pattern.text().strip() or "{track:02d} - {title}"
        fmt = self.combo_format.currentData()

        self.btn_split.setEnabled(False)
        self.lbl_status.setText("Fatiando áudio... Por favor aguarde.")
        self.lbl_status.setStyleSheet("color: #2196f3;")

        try:
            files = split_cue_audio(
                cue_path=cue_path,
                audio_file=audio_path,
                output_dir=out_dir,
                filename_pattern=pattern,
                output_format=fmt
            )
            self.lbl_status.setText(f"Concluído! {len(files)} faixas geradas com sucesso.")
            self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")
            QMessageBox.information(
                None, "Sucesso", f"{len(files)} faixas foram extraídas com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha na extração de faixas: {e}")
            self.lbl_status.setText("Erro durante o fatiamento.")
            self.lbl_status.setStyleSheet("color: #f44336;")
        finally:
            self.btn_split.setEnabled(True)
