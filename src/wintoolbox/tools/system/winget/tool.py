"""
Interface gráfica do Gerenciador de Pacotes e Atualizador de Softwares (winget).
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.winget.logic import (
    build_install_command, build_upgrade_all_command, build_upgrade_command,
    get_curated_apps, is_winget_installed, list_available_upgrades
)
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.winget.ui")


@register
class WingetTool(Tool):
    id = "system.winget"
    name = "Gerenciador e Atualizador Winget"
    category = "Sistema"
    description = "Instalação de programas e atualização de todos os softwares do Windows via winget"
    keywords = ["winget", "atualizar", "instalar", "programas", "softwares", "upgrade", "loja", "apps"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return WingetView(self, parent)


class WingetView(QWidget):
    def __init__(self, tool: WingetTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._process: Optional[QProcess] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        if not is_winget_installed():
            warn_box = QFrame()
            warn_box.setObjectName("Card")
            warn_lay = QVBoxLayout(warn_box)
            lbl = QLabel("O utilitário oficial winget (Windows Package Manager) não foi detectado no sistema.\n"
                         "Certifique-se de que o Instalador de Aplicativos (App Installer) da Microsoft Store está instalado.")
            lbl.setWordWrap(True)
            warn_lay.addWidget(lbl)
            layout.addWidget(warn_box)
            layout.addStretch()
            return

        self.tabs = QTabWidget()
        self._setup_upgrades_tab()
        self._setup_catalog_tab()
        layout.addWidget(self.tabs, stretch=1)

        # Painel de saída do processo
        self.log_panel = LogPanelWidget(title="Saída da Execução (winget)")
        self.log_panel.setMaximumHeight(180)
        layout.addWidget(self.log_panel)

    def _setup_upgrades_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        top_bar = QHBoxLayout()
        self.btn_check_upgrades = QPushButton("Verificar Atualizações")
        self.btn_check_upgrades.clicked.connect(self._check_upgrades_async)
        top_bar.addWidget(self.btn_check_upgrades)

        self.btn_upgrade_all = QPushButton("Atualizar Todos os Programas")
        self.btn_upgrade_all.setProperty("accent", True)
        self.btn_upgrade_all.clicked.connect(self._upgrade_all)
        top_bar.addWidget(self.btn_upgrade_all)

        top_bar.addStretch()
        self.lbl_upgrades_status = QLabel("Clique em 'Verificar Atualizações' para buscar novas versões.")
        top_bar.addWidget(self.lbl_upgrades_status)
        lay.addLayout(top_bar)

        self.table_upgrades = QTableWidget(0, 4)
        self.table_upgrades.setHorizontalHeaderLabels(["Programa", "ID do Pacote", "Versão Atual", "Nova Versão"])
        self.table_upgrades.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_upgrades.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_upgrades.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_upgrades.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        lay.addWidget(self.table_upgrades)

        self.tabs.addTab(tab, "Atualizações Disponíveis")

    def _setup_catalog_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        lbl = QLabel("Catálogo com os principais softwares essenciais para Windows:")
        lay.addWidget(lbl)

        self.table_catalog = QTableWidget(0, 4)
        self.table_catalog.setHorizontalHeaderLabels(["Nome", "Categoria", "ID do Pacote", "Ação"])
        self.table_catalog.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_catalog.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_catalog.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_catalog.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table_catalog.setColumnWidth(3, 110)

        # Preenche catálogo
        apps = get_curated_apps()
        self.table_catalog.setRowCount(len(apps))
        for row, a in enumerate(apps):
            self.table_catalog.setItem(row, 0, QTableWidgetItem(a["name"]))
            self.table_catalog.setItem(row, 1, QTableWidgetItem(a["category"]))
            self.table_catalog.setItem(row, 2, QTableWidgetItem(a["id"]))

            btn_install = QPushButton("Instalar")
            app_id = a["id"]
            btn_install.clicked.connect(lambda _, aid=app_id: self._install_app(aid))
            self.table_catalog.setCellWidget(row, 3, btn_install)

        lay.addWidget(self.table_catalog)
        self.tabs.addTab(tab, "Catálogo de Softwares Populares")

    def _check_upgrades_async(self) -> None:
        self.btn_check_upgrades.setEnabled(False)
        self.lbl_upgrades_status.setText("Consultando repositórios do winget...")

        def _worker():
            return list_available_upgrades()

        def _on_done(upgrades: List[Dict[str, str]]):
            self.btn_check_upgrades.setEnabled(True)
            self.table_upgrades.setRowCount(len(upgrades))
            for row, u in enumerate(upgrades):
                self.table_upgrades.setItem(row, 0, QTableWidgetItem(u["name"]))
                self.table_upgrades.setItem(row, 1, QTableWidgetItem(u["id"]))
                self.table_upgrades.setItem(row, 2, QTableWidgetItem(u["current_version"]))
                self.table_upgrades.setItem(row, 3, QTableWidgetItem(u["available_version"]))

            if upgrades:
                self.lbl_upgrades_status.setText(f"{len(upgrades)} atualizações encontradas.")
            else:
                self.lbl_upgrades_status.setText("Todos os programas compatíveis estão atualizados.")

        def _on_error(err):
            self.btn_check_upgrades.setEnabled(True)
            self.lbl_upgrades_status.setText("Erro ao consultar atualizações.")
            show_toast(self, "Falha na consulta winget", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _run_winget_process(self, cmd_args: List[str]) -> None:
        if self._process and self._process.state() == QProcess.Running:
            show_toast(self, "Outra operação winget já está em andamento.", is_error=True)
            return

        self.log_panel.clear()
        self.log_panel.append_line(f"> {' '.join(cmd_args)}")

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_proc_stdout)
        self._process.readyReadStandardError.connect(self._on_proc_stderr)
        self._process.finished.connect(self._on_proc_finished)

        exe = cmd_args[0]
        args = cmd_args[1:]
        self._process.start(exe, args)

    def _on_proc_stdout(self) -> None:
        if self._process:
            data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            self.log_panel.append_line(data.strip())

    def _on_proc_stderr(self) -> None:
        if self._process:
            data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
            self.log_panel.append_line(data.strip())

    def _on_proc_finished(self, exit_code: int, exit_status) -> None:
        if exit_code == 0:
            self.log_panel.append_line("\nOperação concluída com sucesso.")
            show_toast(self, "Operação winget finalizada!")
        else:
            self.log_panel.append_line(f"\nProcesso finalizado com código {exit_code}.")

    def _install_app(self, app_id: str) -> None:
        cmd = build_install_command(app_id)
        self._run_winget_process(cmd)

    def _upgrade_all(self) -> None:
        cmd = build_upgrade_all_command()
        self._run_winget_process(cmd)
