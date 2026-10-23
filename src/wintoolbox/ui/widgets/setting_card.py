"""
Componente SettingCard estilo Windows 11 Settings / Microsoft PowerToys.
Exibe barra de destaque lateral sutil, título e descrição empilhados, e o controle de ação à direita.
"""
from typing import Optional
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class SettingCard(QFrame):
    """Cartão de configuração horizontal no padrão Fluent Design (100% sem emojis)."""

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str = "",
        control: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setProperty("class", "card")

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(14)

        # Bloco de texto (Título + Descrição)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        text_box.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(description)
        self.lbl_desc.setProperty("class", "secondary")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setVisible(bool(description))
        text_box.addWidget(self.lbl_desc)

        root.addLayout(text_box, stretch=1)

        # Container de controles à direita
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(8)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        if control is not None:
            self.controls_layout.addWidget(control)
        root.addLayout(self.controls_layout)

    def add_control(self, widget: QWidget) -> None:
        """Adiciona um widget de controle ao lado direito do cartão."""
        self.controls_layout.addWidget(widget)

    def set_title(self, text: str) -> None:
        self.lbl_title.setText(text)

    def set_description(self, text: str) -> None:
        self.lbl_desc.setText(text)
        self.lbl_desc.setVisible(bool(text))
