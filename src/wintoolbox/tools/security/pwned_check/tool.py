"""
Interface gráfica do Verificador de Senhas Vazadas (Have I Been Pwned com k-anonimato).
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.security.pwned_check.logic import check_password_pwned
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("security.pwned_check.ui")


@register
class PwnedCheckTool(Tool):
    id = "security.pwned_check"
    name = "Verificador de Senhas Vazadas"
    category = "Segurança"
    description = "Consulta anônima e segura (k-anonimato HIBP) para verificar se uma senha foi exposta em vazamentos de dados públicos"
    keywords = ["senha", "vazamento", "have i been pwned", "pwned", "seguranca", "breach", "credencial", "k-anonimato"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PwnedCheckView(self, parent)


class PwnedCheckView(QWidget):
    def __init__(self, tool: PwnedCheckTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        # Aviso explicativo sobre Privacidade e k-anonimato
        info_card = QFrame()
        info_card.setObjectName("Card")
        i_lay = QVBoxLayout(info_card)
        i_lay.setContentsMargins(14, 12, 14, 12)
        lbl_info_title = QLabel("<b>Privacidade e Segurança por Design (k-Anonimato):</b>")
        lbl_info_desc = QLabel(
            "Sua senha real NUNCA é enviada pela rede. O WinToolbox calcula o hash criptográfico SHA-1 localmente\n"
            "e envia apenas os 5 primeiros caracteres à API oficial do Have I Been Pwned. A comparação final\n"
            "é realizada exclusivamente na sua própria máquina."
        )
        lbl_info_desc.setStyleSheet("color: #888888;")
        lbl_info_desc.setWordWrap(True)
        i_lay.addWidget(lbl_info_title)
        i_lay.addWidget(lbl_info_desc)
        layout.addWidget(info_card)

        # Entrada de senha
        input_card = QFrame()
        input_card.setObjectName("Card")
        in_lay = QVBoxLayout(input_card)
        in_lay.setContentsMargins(16, 16, 16, 16)
        in_lay.setSpacing(10)

        in_lay.addWidget(QLabel("Digite a senha para verificação:"))
        pwd_row = QHBoxLayout()
        self.txt_pwd = QLineEdit()
        self.txt_pwd.setEchoMode(QLineEdit.Password)
        self.txt_pwd.setPlaceholderText("Digite a senha para checar...")
        self.txt_pwd.returnPressed.connect(self._check_password)
        pwd_row.addWidget(self.txt_pwd, stretch=1)

        self.btn_toggle_vis = QPushButton("Mostrar")
        self.btn_toggle_vis.clicked.connect(self._toggle_visibility)
        pwd_row.addWidget(self.btn_toggle_vis)

        self.btn_check = QPushButton("Verificar Vazamento")
        self.btn_check.setProperty("accent", True)
        self.btn_check.clicked.connect(self._check_password)
        pwd_row.addWidget(self.btn_check)

        in_lay.addLayout(pwd_row)
        layout.addWidget(input_card)

        # Card de Resultado
        self.result_card = QFrame()
        self.result_card.setObjectName("Card")
        r_lay = QVBoxLayout(self.result_card)
        r_lay.setContentsMargins(16, 16, 16, 16)
        r_lay.setSpacing(8)

        self.lbl_result_title = QLabel("Resultado da Auditoria:")
        self.lbl_result_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        r_lay.addWidget(self.lbl_result_title)

        self.lbl_result_msg = QLabel("Digite uma senha acima e clique em 'Verificar Vazamento'.")
        self.lbl_result_msg.setWordWrap(True)
        r_lay.addWidget(self.lbl_result_msg)

        layout.addWidget(self.result_card)
        layout.addStretch()

    def _toggle_visibility(self) -> None:
        if self.txt_pwd.echoMode() == QLineEdit.Password:
            self.txt_pwd.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_vis.setText("Ocultar")
        else:
            self.txt_pwd.setEchoMode(QLineEdit.Password)
            self.btn_toggle_vis.setText("Mostrar")

    def _check_password(self) -> None:
        pwd = self.txt_pwd.text()
        if not pwd:
            show_toast(self, "Digite uma senha para checar.", is_error=True)
            return

        self.btn_check.setEnabled(False)
        self.lbl_result_msg.setText("Consultando base de dados com k-anonimato...")

        def _worker():
            return check_password_pwned(pwd)

        def _on_done(result):
            self.btn_check.setEnabled(True)
            is_pwned, count, msg = result

            if is_pwned:
                self.lbl_result_title.setText("ALERTA: Senha Comprometida em Vazamentos!")
                self.lbl_result_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #d83b01;")
                self.lbl_result_msg.setText(msg)
                show_toast(self, f"Atenção: Senha encontrada em {count:,} vazamento(s)!", is_error=True)
            else:
                self.lbl_result_title.setText("Senha Segura e Não Exposta")
                self.lbl_result_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #107c41;")
                self.lbl_result_msg.setText(msg)
                show_toast(self, "Nenhum vazamento detectado para esta senha!")

        def _on_error(err):
            self.btn_check.setEnabled(True)
            self.lbl_result_msg.setText(f"Erro na verificação: {err}")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
