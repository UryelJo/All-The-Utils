"""
Sistema de Notificações Não-Bloqueantes (Toast / InfoBar) integrado à janela.
Permite exibir feedback imediato de sucesso, aviso, erro ou informação sem emojis e sem travar a UI.
"""
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from wintoolbox.ui.theme import get_current_tokens


class ToastWidget(QFrame):
    """Banner flutuante não-bloqueante exibido no canto superior direito da janela."""

    def __init__(
        self,
        parent: QWidget,
        title: str,
        message: str = "",
        kind: str = "info",  # 'success' | 'warning' | 'error' | 'info'
        duration_ms: int = 3500,
    ):
        super().__init__(parent)
        self.setFixedWidth(360)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        t = get_current_tokens()
        color_map = {
            "success": t.status_success,
            "warning": t.status_warning,
            "error": t.status_danger,
            "info": t.accent,
        }
        accent_col = color_map.get(kind, t.accent)

        self.setStyleSheet(f"""
            ToastWidget {{
                background-color: {t.bg_card};
                border: 1px solid {t.border_color};
                border-left: 4px solid {accent_col};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {t.text_primary}; background: transparent;")
        text_col.addWidget(lbl_title)

        if message:
            lbl_msg = QLabel(message)
            lbl_msg.setWordWrap(True)
            lbl_msg.setStyleSheet(f"font-size: 12px; color: {t.text_secondary}; background: transparent;")
            text_col.addWidget(lbl_msg)

        layout.addLayout(text_col, stretch=1)

        btn_close = QPushButton("Fechar")
        btn_close.setProperty("class", "ghost")
        btn_close.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignTop)

        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.close)

    def _reposition(self) -> None:
        p = self.parentWidget()
        if p:
            x = max(16, p.width() - self.width() - 24)
            y = 56
            self.move(x, y)


def show_toast(
    context_widget: Optional[QWidget],
    title: str,
    message: str = "",
    kind: str = "info",
    duration_ms: int = 3500,
    is_error: bool = False,
) -> Optional[ToastWidget]:
    """Exibe um Toast não-bloqueante na janela principal da aplicação."""
    if context_widget is None:
        return None
    top_win = context_widget.window()
    if top_win is None:
        return None
    if is_error and kind == "info":
        kind = "error"
    return ToastWidget(
        parent=top_win,
        title=title,
        message=message,
        kind=kind,
        duration_ms=duration_ms,
    )
