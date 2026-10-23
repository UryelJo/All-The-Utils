"""
Barra de Ação Inferior (Action Bar Widget).
Contém barra de progresso, botões de execução/cancelamento e atalhos pós-lote.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget
)

class ActionBarWidget(QFrame):
    """Barra inferior de controle para ferramentas."""
    start_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, action_title: str = "Iniciar Processamento", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._last_output_dir: Optional[Path] = None

        self._build_ui(action_title)

    def _build_ui(self, action_title: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Botão Primário
        self.btn_primary = QPushButton(action_title)
        self.btn_primary.setProperty("class", "primary")
        self.btn_primary.setMinimumWidth(160)
        self.btn_primary.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self.btn_primary)

        # Botão Cancelar
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
        layout.addWidget(self.btn_cancel)

        # Barra de Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar, stretch=1)

        # Botão Abrir Pasta (visível após sucesso)
        self.btn_open_folder = QPushButton("Abrir Pasta de Destino")
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.clicked.connect(self._open_output_dir)
        layout.addWidget(self.btn_open_folder)

    def set_running(self, running: bool):
        self.btn_primary.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        if running:
            self.btn_open_folder.setVisible(False)
            self.progress_bar.setValue(0)

    def update_progress(self, current: int, total: int, message: str = ""):
        if total > 0:
            val = int((current / total) * 100)
            self.progress_bar.setValue(val)
            self.progress_bar.setFormat(f"{current}/{total} ({val}%) - {message}")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(message)

    def set_finished(self, output_dir: Optional[Path] = None):
        self.set_running(False)
        self.progress_bar.setValue(100)
        if output_dir and output_dir.exists():
            self._last_output_dir = output_dir
            self.btn_open_folder.setVisible(True)

    def _open_output_dir(self):
        if self._last_output_dir and self._last_output_dir.exists():
            subprocess.Popen(f'explorer "{self._last_output_dir}"')
