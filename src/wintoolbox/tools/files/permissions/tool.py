"""
Interface gráfica do Reparador de Permissões NTFS do Windows.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.files.permissions.logic import repair_ntfs_permissions
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("files.permissions.ui")


@register
class PermissionsTool(Tool):
    id = "files.permissions"
    name = "Permissões NTFS e Acesso Negado"
    category = "Arquivos e Pastas"
    description = "Apropriação de posse (takeown) e redefinição de permissões de arquivos ou pastas inacessíveis"
    keywords = ["permissoes", "acesso negado", "takeown", "icacls", "ntfs", "posse", "bloqueado", "seguranca"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PermissionsView(self, parent)


class PermissionsView(QWidget):
    def __init__(self, tool: PermissionsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        # Seletor de alvo
        box = QGroupBox("Item Bloqueado ou Inacessível")
        b_lay = QVBoxLayout(box)
        b_lay.setContentsMargins(14, 14, 14, 14)
        b_lay.setSpacing(10)

        path_row = QHBoxLayout()
        self.txt_target = QLineEdit()
        self.txt_target.setPlaceholderText("Selecione um arquivo ou pasta para reparar permissões...")
        path_row.addWidget(self.txt_target, stretch=1)

        btn_file = QPushButton("Arquivo...")
        btn_file.clicked.connect(self._browse_file)
        path_row.addWidget(btn_file)

        btn_folder = QPushButton("Pasta...")
        btn_folder.clicked.connect(self._browse_folder)
        path_row.addWidget(btn_folder)
        b_lay.addLayout(path_row)

        # Opções de reparo
        b_lay.addWidget(QLabel("Ações a serem executadas:"))
        self.chk_ownership = QCheckBox("Tomar posse do item para o Administrador (takeown)")
        self.chk_ownership.setChecked(True)
        b_lay.addWidget(self.chk_ownership)

        self.chk_reset = QCheckBox("Redefinir permissões herdadas padrão (icacls /reset)")
        self.chk_reset.setChecked(True)
        b_lay.addWidget(self.chk_reset)

        self.chk_grant = QCheckBox("Conceder Controle Total explícito para a conta do usuário atual")
        self.chk_grant.setChecked(True)
        b_lay.addWidget(self.chk_grant)

        self.btn_run = QPushButton("Reparar Permissões NTFS")
        self.btn_run.setProperty("accent", True)
        self.btn_run.setFixedWidth(200)
        self.btn_run.clicked.connect(self._run_repair_async)
        b_lay.addWidget(self.btn_run)

        layout.addWidget(box)

        self.log_panel = LogPanelWidget(title="Registro de Execução de Permissões")
        layout.addWidget(self.log_panel, stretch=1)

    def _browse_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo Inacessível", "", "Todos os Arquivos (*.*)")
        if p:
            self.txt_target.setText(p)

    def _browse_folder(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Selecionar Pasta Inacessível", "")
        if p:
            self.txt_target.setText(p)

    def _run_repair_async(self) -> None:
        target = self.txt_target.text().strip()
        if not target:
            show_toast(self, "Selecione um arquivo ou pasta primeiro.", is_error=True)
            return

        self.btn_run.setEnabled(False)
        self.log_panel.clear()
        self.log_panel.append_line(f"Iniciando reparo em '{target}'...")

        take_own = self.chk_ownership.isChecked()
        reset_acl = self.chk_reset.isChecked()
        grant_u = self.chk_grant.isChecked()

        def _worker():
            return repair_ntfs_permissions(Path(target), take_own, reset_acl, grant_u)

        def _on_done(result):
            self.btn_run.setEnabled(True)
            ok, output = result
            self.log_panel.append_line(output)
            if ok:
                show_toast(self, "Permissões NTFS reparadas com sucesso!")
            else:
                show_toast(self, "Falha no reparo de permissões.", is_error=True)

        def _on_error(err):
            self.btn_run.setEnabled(True)
            self.log_panel.append_line(f"Erro: {err}")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
