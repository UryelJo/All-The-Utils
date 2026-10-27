"""
Interface de usuário para a ferramenta Folha de Contato de Vídeo.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QGuiApplication, QPixmap
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
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.media.contact_sheet.logic import generate_contact_sheet


@register
class ContactSheetTool(Tool):
    """Gerador de mosaicos e folhas de contato de vídeo (Video Contact Sheet)."""

    id = "media.contact_sheet"
    name = "Folha de Contato de Vídeo"
    description = "Gera mosaicos visuais (thumbnails grid) com metadados e timecode para pré-visualização rápida de vídeos."
    category = "media"

    def __init__(self):
        super().__init__()
        self.last_generated_path: Path = None

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Folha de Contato de Vídeo")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Crie sumários visuais completos de vídeos com grade de miniaturas em alta definição, "
            "marcações de tempo e ficha técnica."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Painel de Seleção e Opções
        config_frame = QFrame()
        config_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(config_frame)
        grid.setSpacing(10)

        # Arquivo de Vídeo
        grid.addWidget(QLabel("Arquivo de Vídeo:"), 0, 0)
        self.txt_video_path = QLineEdit()
        self.txt_video_path.setPlaceholderText("Selecione um arquivo de vídeo...")
        self.btn_browse = QPushButton("Procurar...")
        self.btn_browse.clicked.connect(self._browse_video)
        grid.addWidget(self.txt_video_path, 0, 1, 1, 3)
        grid.addWidget(self.btn_browse, 0, 4)

        # Linhas e Colunas
        grid.addWidget(QLabel("Linhas:"), 1, 0)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 12)
        self.spin_rows.setValue(4)
        grid.addWidget(self.spin_rows, 1, 1)

        grid.addWidget(QLabel("Colunas:"), 1, 2)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 12)
        self.spin_cols.setValue(4)
        grid.addWidget(self.spin_cols, 1, 3)

        # Largura da Folha
        grid.addWidget(QLabel("Largura da Imagem:"), 2, 0)
        self.combo_width = QComboBox()
        self.combo_width.addItem("1280 px (HD)", 1280)
        self.combo_width.addItem("1920 px (Full HD)", 1920)
        self.combo_width.addItem("2560 px (2K QHD)", 2560)
        self.combo_width.addItem("3840 px (4K UHD)", 3840)
        self.combo_width.setCurrentIndex(1)
        grid.addWidget(self.combo_width, 2, 1)

        # Checkboxes
        check_layout = QHBoxLayout()
        self.check_metadata = QCheckBox("Exibir Cabeçalho de Metadados")
        self.check_metadata.setChecked(True)
        self.check_timecode = QCheckBox("Exibir Marcação de Tempo (Timecode)")
        self.check_timecode.setChecked(True)
        check_layout.addWidget(self.check_metadata)
        check_layout.addWidget(self.check_timecode)
        grid.addLayout(check_layout, 2, 2, 1, 3)

        layout.addWidget(config_frame)

        # Botão Gerar
        self.btn_generate = QPushButton("Gerar Folha de Contato")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_generate.clicked.connect(self._generate_sheet)
        layout.addWidget(self.btn_generate)

        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        # Área de Pré-Visualização
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(300)

        self.lbl_preview = QLabel("Nenhuma folha de contato gerada ainda.")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("color: #888888;")
        self.scroll_area.setWidget(self.lbl_preview)
        layout.addWidget(self.scroll_area, 1)

        # Barra de Ações Inferior
        actions_layout = QHBoxLayout()
        self.btn_copy_image = QPushButton("Copiar para Área de Transferência")
        self.btn_copy_image.setEnabled(False)
        self.btn_copy_image.clicked.connect(self._copy_to_clipboard)

        self.btn_save_as = QPushButton("Salvar Como...")
        self.btn_save_as.setEnabled(False)
        self.btn_save_as.clicked.connect(self._save_as)

        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_copy_image)
        actions_layout.addWidget(self.btn_save_as)
        layout.addLayout(actions_layout)

        return widget

    def _browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Arquivo de Vídeo",
            "",
            "Vídeos (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts *.m4v)"
        )
        if file_path:
            self.txt_video_path.setText(file_path)

    def _generate_sheet(self):
        video_raw = self.txt_video_path.text().strip()
        if not video_raw:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo de vídeo primeiro.")
            return

        video_path = Path(video_raw)
        if not video_path.is_file():
            QMessageBox.critical(None, "Erro", "O arquivo de vídeo selecionado não existe.")
            return

        rows = self.spin_rows.value()
        cols = self.spin_cols.value()
        width = self.combo_width.currentData() or 1920
        show_meta = self.check_metadata.isChecked()
        show_tc = self.check_timecode.isChecked()

        # Define caminho de saída padrão no mesmo diretório
        out_path = video_path.parent / f"{video_path.stem}_contact_sheet.jpg"

        self.btn_generate.setEnabled(False)
        self.lbl_status.setText("Extraindo quadros e montando folha de contato...")
        self.lbl_status.setStyleSheet("color: #2196f3;")

        try:
            res_path = generate_contact_sheet(
                video_path=video_path,
                output_path=out_path,
                rows=rows,
                cols=cols,
                sheet_width=width,
                show_metadata=show_meta,
                show_timecode=show_tc
            )
            self.last_generated_path = res_path

            # Carrega pré-visualização
            pixmap = QPixmap(str(res_path))
            if not pixmap.isNull():
                scaled = pixmap.scaledToWidth(800, Qt.TransformationMode.SmoothTransformation)
                self.lbl_preview.setPixmap(scaled)
                self.lbl_preview.setText("")
            self.btn_copy_image.setEnabled(True)
            self.btn_save_as.setEnabled(True)

            self.lbl_status.setText(f"Folha de contato salva em: {res_path.name}")
            self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")
        except Exception as e:
            QMessageBox.critical(None, "Erro na Geração", f"Falha ao gerar folha de contato: {e}")
            self.lbl_status.setText("Erro ao gerar folha de contato.")
            self.lbl_status.setStyleSheet("color: #f44336;")
        finally:
            self.btn_generate.setEnabled(True)

    def _copy_to_clipboard(self):
        if self.last_generated_path and self.last_generated_path.is_file():
            clipboard = QGuiApplication.clipboard()
            pixmap = QPixmap(str(self.last_generated_path))
            clipboard.setPixmap(pixmap)
            QMessageBox.information(
                None, "Copiado", "A imagem da folha de contato foi copiada para a área de transferência!"
            )

    def _save_as(self):
        if not self.last_generated_path or not self.last_generated_path.is_file():
            return
        dest, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Folha de Contato Como",
            str(self.last_generated_path.name),
            "Imagem JPEG (*.jpg);;Imagem PNG (*.png)"
        )
        if dest:
            import shutil
            shutil.copy2(self.last_generated_path, dest)
            QMessageBox.information(None, "Salvo", f"Imagem salva em: {dest}")
