"""
Interface gráfica do Ajustador de Menu de Contexto do Windows 11.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.context_menu.logic import (
    is_classic_context_menu_enabled, restart_explorer, set_classic_context_menu
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.context_menu.ui")


@register
class ContextMenuTool(Tool):
    id = "system.context_menu"
    name = "Menu de Contexto do Windows 11"
    category = "Sistema"
    description = "Restaura o menu de contexto clássico completo do botão direito sem precisar clicar em 'Mostrar mais opções'"
    keywords = ["menu de contexto", "botao direito", "classico", "windows 11", "mostrar mais opcoes", "explorer", "personalizar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ContextMenuView(self, parent)


class ContextMenuView(QWidget):
    def __init__(self, tool: ContextMenuTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Card de Status Atual
        self.card_status = QFrame()
        self.card_status.setObjectName("Card")
        c_lay = QVBoxLayout(self.card_status)
        c_lay.setContentsMargins(16, 16, 16, 16)
        c_lay.setSpacing(8)

        lbl_title = QLabel("Status Atual do Menu de Contexto do Explorer:")
        lbl_title.setStyleSheet("font-size: 13px; color: #888888;")
        c_lay.addWidget(lbl_title)

        self.lbl_current_mode = QLabel()
        self.lbl_current_mode.setStyleSheet("font-size: 16px; font-weight: bold;")
        c_lay.addWidget(self.lbl_current_mode)

        self.lbl_desc_mode = QLabel()
        self.lbl_desc_mode.setWordWrap(True)
        c_lay.addWidget(self.lbl_desc_mode)

        layout.addWidget(self.card_status)

        # Controles de Alternância
        actions_card = QFrame()
        actions_card.setObjectName("Card")
        a_lay = QVBoxLayout(actions_card)
        a_lay.setContentsMargins(16, 16, 16, 16)
        a_lay.setSpacing(12)

        btn_row = QHBoxLayout()
        self.btn_enable_classic = QPushButton("Ativar Menu Clássico Completo")
        self.btn_enable_classic.setProperty("accent", True)
        self.btn_enable_classic.clicked.connect(lambda: self._apply(True))
        btn_row.addWidget(self.btn_enable_classic)

        self.btn_restore_modern = QPushButton("Restaurar Menu Moderno do Windows 11")
        self.btn_restore_modern.clicked.connect(lambda: self._apply(False))
        btn_row.addWidget(self.btn_restore_modern)

        a_lay.addLayout(btn_row)

        self.chk_restart = QCheckBox("Reiniciar o Windows Explorer automaticamente para aplicar a alteração agora")
        self.chk_restart.setChecked(True)
        a_lay.addWidget(self.chk_restart)

        layout.addWidget(actions_card)

        # Botão avulso de reiniciar Explorer
        extra_row = QHBoxLayout()
        btn_restart_exp = QPushButton("Reiniciar Processo do Explorer Manualmente")
        btn_restart_exp.clicked.connect(self._restart_explorer_manual)
        extra_row.addWidget(btn_restart_exp)
        extra_row.addStretch()
        layout.addLayout(extra_row)

        layout.addStretch()
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        is_classic = is_classic_context_menu_enabled()
        if is_classic:
            self.lbl_current_mode.setText("Menu Clássico Completo (Estilo Windows 10)")
            self.lbl_current_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #107c41;")
            self.lbl_desc_mode.setText("Todas as opções de terceiros e ações aparecem diretamente no clique com o botão direito, sem ocultação.")
            self.btn_enable_classic.setEnabled(False)
            self.btn_restore_modern.setEnabled(True)
        else:
            self.lbl_current_mode.setText("Menu Moderno Padrão (Estilo Windows 11)")
            self.lbl_current_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #0078d4;")
            self.lbl_desc_mode.setText("Menu simplificado nativo do Windows 11 com barra de ícones rápidos e botão 'Mostrar mais opções'.")
            self.btn_enable_classic.setEnabled(True)
            self.btn_restore_modern.setEnabled(False)

    def _apply(self, enable_classic: bool) -> None:
        ok, msg = set_classic_context_menu(enable_classic)
        if ok:
            show_toast(self, msg)
            if self.chk_restart.isChecked():
                restart_explorer()
            self._refresh_ui()
        else:
            show_toast(self, msg, is_error=True)

    def _restart_explorer_manual(self) -> None:
        ok, msg = restart_explorer()
        if ok:
            show_toast(self, msg)
        else:
            show_toast(self, msg, is_error=True)
