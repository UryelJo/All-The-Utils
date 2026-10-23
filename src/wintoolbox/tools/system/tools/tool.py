"""
Ferramenta: Ferramentas e Manutenção do Windows.
Implementação gráfica com suporte a execução assíncrona e logs em tempo real.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, ToolResult, register
from wintoolbox.core.shell import run_command_streaming
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.tools.logic import clean_temp_directory
from wintoolbox.ui.widgets.log_panel import LogPanelWidget

@register
class SystemToolsTool(Tool):
    id = "system.tools"
    name = "Ferramentas do Windows"
    category = "Sistema"
    description = "Diagnóstico, reparo, limpeza de cache DNS, integridade (SFC) e otimização de disco"
    keywords = ["sistema", "manutenção", "disco", "sfc", "defrag", "dns", "temp", "limpeza", "reparo"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SystemToolsView(self, parent)

class SystemToolsView(QWidget):
    def __init__(self, tool: SystemToolsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()

        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Alerta de privilégios de Administrador
        admin_card = QFrame()
        admin_card.setProperty("class", "card")
        admin_layout = QHBoxLayout(admin_card)
        admin_layout.setContentsMargins(12, 10, 12, 10)

        admin_status = "Executando como Administrador" if is_admin() else "Executando como Usuário Padrão"
        self.lbl_admin = QLabel(f"Status UAC: {admin_status}")
        self.lbl_admin.setStyleSheet("font-weight: 500;")
        admin_layout.addWidget(self.lbl_admin)

        admin_layout.addStretch()

        if not is_admin():
            btn_elevate = QPushButton("Executar como Administrador")
            btn_elevate.clicked.connect(self._on_elevate)
            admin_layout.addWidget(btn_elevate)

        layout.addWidget(admin_card)

        # Grade de Ações
        grid_card = QFrame()
        grid_card.setProperty("class", "card")
        grid_layout = QGridLayout(grid_card)
        grid_layout.setContentsMargins(14, 14, 14, 14)
        grid_layout.setSpacing(12)

        # 1. Otimizar Disco
        btn_defrag = QPushButton("Otimizar e Desfragmentar Unidade C:")
        btn_defrag.clicked.connect(lambda: self._run_command("defrag C: /O", requires_admin=True))
        grid_layout.addWidget(btn_defrag, 0, 0)

        # 2. Limpar Temporários
        btn_temp = QPushButton("Limpar Arquivos Temporários (%TEMP%)")
        btn_temp.clicked.connect(self._run_clean_temp)
        grid_layout.addWidget(btn_temp, 0, 1)

        # 3. SFC Scannow
        btn_sfc = QPushButton("Verificar Integridade de Arquivos (SFC)")
        btn_sfc.clicked.connect(lambda: self._run_command("sfc /scannow", requires_admin=True))
        grid_layout.addWidget(btn_sfc, 1, 0)

        # 4. Flush DNS
        btn_dns = QPushButton("Limpar Cache de DNS (Flush DNS)")
        btn_dns.clicked.connect(lambda: self._run_command("ipconfig /flushdns", requires_admin=False))
        grid_layout.addWidget(btn_dns, 1, 1)

        layout.addWidget(grid_card)

        # Painel de Log
        self.log_panel = LogPanelWidget()
        layout.addWidget(self.log_panel)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _on_elevate(self):
        if request_elevation():
            self.lbl_admin.setText("Reiniciando com elevação...")

    def _run_clean_temp(self):
        self.log_panel.append_log("INFO", "Iniciando limpeza de arquivos temporários...")
        def worker(ctx):
            clean_temp_directory(lambda msg: ctx.on_log("INFO", msg))
            return ToolResult(success=True, message="Limpeza concluída.")
        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )

    def _run_command(self, cmd_str: str, requires_admin: bool = False):
        if requires_admin and not is_admin():
            res = QMessageBox.question(
                self,
                "Privilégios Necessários",
                f"O comando '{cmd_str}' necessita de privilégios de Administrador.\n"
                "Deseja reiniciar a aplicação como Administrador agora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.Yes:
                request_elevation()
            return

        self.log_panel.append_log("INFO", f"Executando comando: {cmd_str}")

        def worker(ctx):
            code = run_command_streaming(
                cmd=cmd_str,
                on_output=lambda line: ctx.on_log("INFO", line),
                shell=True,
                is_cancelled=ctx.is_cancelled
            )
            return ToolResult(
                success=(code == 0),
                message=f"Comando finalizado com código de retorno: {code}"
            )

        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg)
        )
