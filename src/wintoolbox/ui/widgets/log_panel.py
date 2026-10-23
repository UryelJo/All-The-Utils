"""
Painel de Log Recolhível (Log Panel Widget).
Apresenta saídas de console e mensagens em fonte monoespaçada limpa,
adaptando-se automaticamente ao Tema Escuro e Claro.
"""
import time
from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.ui.widgets.toast import show_toast


class LogPanelWidget(QFrame):
    """Componente recolhível para exibição de logs e saídas de terminal."""

    # Permite chamar append_log de threads de trabalho (ex: servidor HTTP) com segurança
    _log_requested = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._is_collapsed = False
        self._log_requested.connect(self._append_log_ui)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_toggle = QPushButton("Log de Execução (Ocultar)")
        self.btn_toggle.setProperty("class", "ghost")
        self.btn_toggle.setStyleSheet("font-weight: 600; text-align: left; padding: 2px 4px;")
        self.btn_toggle.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self.btn_toggle)

        header_layout.addStretch()

        self.btn_copy = QPushButton("Copiar Log")
        self.btn_copy.setStyleSheet("font-size: 11px; padding: 3px 10px; min-height: 20px;")
        self.btn_copy.clicked.connect(self._copy_log)
        header_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("Limpar Log")
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 3px 10px; min-height: 20px;")
        self.btn_clear.clicked.connect(self.clear)
        header_layout.addWidget(self.btn_clear)

        layout.addLayout(header_layout)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Cascadia Mono, Consolas, Courier New", 9))
        self.txt_log.setFixedHeight(125)
        layout.addWidget(self.txt_log)

    def toggle_collapse(self) -> None:
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.txt_log.setVisible(False)
            self.btn_clear.setVisible(False)
            self.btn_copy.setVisible(False)
            self.btn_toggle.setText("Log de Execução (Expandir)")
        else:
            self.txt_log.setVisible(True)
            self.btn_clear.setVisible(True)
            self.btn_copy.setVisible(True)
            self.btn_toggle.setText("Log de Execução (Ocultar)")

    def append_log(self, level: str, message: str) -> None:
        self._log_requested.emit(level, message)

    def _append_log_ui(self, level: str, message: str) -> None:
        now = time.strftime("%H:%M:%S")
        prefix = f"[{now}] [{level.upper()}]"
        self.txt_log.appendPlainText(f"{prefix} {message}")
        self.txt_log.moveCursor(QTextCursor.End)

    def _copy_log(self) -> None:
        text = self.txt_log.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            show_toast(self, "Log Copiado", "Saída copiada para a área de transferência.", kind="success")

    def clear(self) -> None:
        self.txt_log.clear()
