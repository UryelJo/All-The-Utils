"""
Widget Seletor de Destino e Políticas de Saída (Output Picker Widget).
Permite configurar pasta de saída, subpasta personalizada, espelhamento
de estrutura e regras de conflito.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.batch import OutputPolicy
from wintoolbox.core.settings import load_settings

class OutputPickerWidget(QFrame):
    """Componente para configurar o destino do processamento em lote."""
    policy_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._custom_path: Optional[Path] = None

        self._build_ui()
        self._load_defaults()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl_header = QLabel("Destino e Política de Saída")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        # Linha 1: Modo de Destino e Caminho
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_dest = QLabel("Salvar em:")
        lbl_dest.setFixedWidth(80)
        row1.addWidget(lbl_dest)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems([
            "Subpasta dentro da pasta original",
            "Mesma pasta do arquivo original",
            "Pasta personalizada..."
        ])
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        row1.addWidget(self.cmb_mode, stretch=1)

        self.txt_subfolder = QLineEdit("convertidos")
        self.txt_subfolder.setPlaceholderText("Nome da subpasta")
        self.txt_subfolder.setFixedWidth(130)
        row1.addWidget(self.txt_subfolder)

        self.btn_browse = QPushButton("Procurar...")
        self.btn_browse.setVisible(False)
        self.btn_browse.clicked.connect(self._on_browse)
        row1.addWidget(self.btn_browse)

        layout.addLayout(row1)

        # Linha 2: Espelhamento e Resolução de Conflitos
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.chk_mirror = QCheckBox("Espelhar estrutura de subpastas")
        self.chk_mirror.setChecked(True)
        row2.addWidget(self.chk_mirror)

        row2.addSpacing(20)

        lbl_conflict = QLabel("Se o arquivo já existir:")
        row2.addWidget(lbl_conflict)

        self.cmb_conflict = QComboBox()
        self.cmb_conflict.addItems([
            "Renomear com sufixo (1)",
            "Sobrescrever arquivo",
            "Pular arquivo"
        ])
        row2.addWidget(self.cmb_conflict)

        row2.addStretch()
        layout.addLayout(row2)

    def _load_defaults(self):
        st = load_settings()
        mode = st.get("default_output_mode", "subfolder")
        if mode == "same_folder":
            self.cmb_mode.setCurrentIndex(1)
        elif mode == "custom":
            self.cmb_mode.setCurrentIndex(2)
        else:
            self.cmb_mode.setCurrentIndex(0)

        self.txt_subfolder.setText(st.get("default_subfolder_name", "convertidos"))
        self._on_mode_changed(self.cmb_mode.currentIndex())

    def _on_mode_changed(self, idx: int):
        if idx == 0:  # Subpasta
            self.txt_subfolder.setVisible(True)
            self.btn_browse.setVisible(False)
        elif idx == 1:  # Mesma pasta
            self.txt_subfolder.setVisible(False)
            self.btn_browse.setVisible(False)
        elif idx == 2:  # Personalizada
            self.txt_subfolder.setVisible(False)
            self.btn_browse.setVisible(True)
        self.policy_changed.emit()

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino")
        if folder:
            self._custom_path = Path(folder)
            self.btn_browse.setText(self._custom_path.name or str(self._custom_path))
            self.policy_changed.emit()

    def get_policy(self) -> OutputPolicy:
        idx = self.cmb_mode.currentIndex()
        if idx == 0:
            mode = "subfolder"
        elif idx == 1:
            mode = "same_folder"
        else:
            mode = "custom"

        conflict_idx = self.cmb_conflict.currentIndex()
        conflict_map = {0: "rename", 1: "overwrite", 2: "skip"}

        return OutputPolicy(
            mode=mode,
            subfolder_name=self.txt_subfolder.text().strip() or "convertidos",
            custom_dir=self._custom_path,
            mirror_structure=self.chk_mirror.isChecked(),
            conflict=conflict_map.get(conflict_idx, "rename"),
            preserve_timestamps=True
        )
