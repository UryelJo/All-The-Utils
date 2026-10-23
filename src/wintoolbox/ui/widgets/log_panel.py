"""
Painel de Log Recolhível (Log Panel Widget).
Apresenta saídas de console e mensagens em fonte monoespaçada limpa.
"""
import time
from typing import Optional
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
)

class LogPanelWidget(QFrame):
    """Componente recolhível para exibição de logs e saídas de terminal."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._is_collapsed = False

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Barra do cabeçalho
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_toggle = QPushButton("▼ Log de Execução")
        self.btn_toggle.setStyleSheet("border: none; background: transparent; font-weight: 600; text-align: left; padding: 0;")
        self.btn_toggle.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self.btn_toggle)

        header_layout.addStretch()

        self.btn_clear = QPushButton("Limpar Log")
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 2px 8px; min-height: 18px;")
        self.btn_clear.clicked.connect(self.clear)
        header_layout.addWidget(self.btn_clear)

        layout.addLayout(header_layout)

        # Caixa de texto
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Cascadia Mono, Consolas, Courier New", 9))
        self.txt_log.setFixedHeight(120)
        self.txt_log.setStyleSheet("background-color: #1a1a1a; color: #d4d4d4; border: 1px solid #333333;")
        layout.addWidget(self.txt_log)

    def toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.txt_log.setVisible(False)
            self.btn_clear.setVisible(False)
            self.btn_toggle.setText("► Log de Execução (Oculto)")
        else:
            self.txt_log.setVisible(True)
            self.btn_clear.setVisible(True)
            self.btn_toggle.setText("▼ Log de Execução")

    def append_log(self, level: str, message: str):
        now = time.strftime("%H:%M:%S")
        prefix = f"[{now}] [{level.upper()}]"
        self.txt_log.appendPlainText(f"{prefix} {message}")
        self.txt_log.moveCursor(QTextCursor.End)

    def clear(self):
        self.txt_log.clear()
