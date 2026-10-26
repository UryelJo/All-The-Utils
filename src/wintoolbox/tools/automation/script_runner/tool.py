"""
Interface gráfica do Executor de Scripts.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.script_runner.logic import (
    add_or_update_script_entry, build_script_command, delete_script_entry,
    load_saved_scripts
)
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

_log = get_logger("automation.script_runner.ui")


@register
class ScriptRunnerTool(Tool):
    id = "automation.script_runner"
    name = "Executor de Scripts"
    category = "Automação"
    description = "Execução centralizada de scripts PowerShell, Python, Batch e VBS com saída de console em tempo real"
    keywords = ["script", "powershell", "batch", "cmd", "python", "executar", "console", "runner", "automacao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ScriptRunnerView(self, parent)


class ScriptRunnerView(QWidget):
    def __init__(self, tool: ScriptRunnerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._process: Optional[QProcess] = None
        self._saved_scripts: List[Dict[str, Any]] = []

        self._build_ui()
        self._refresh_saved_scripts()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Executor Centralizado de Scripts",
            "Dispare rotinas PowerShell, scripts Python ou lotes .bat com controle de parâmetros e log de console."
        ))

        # 1. Formulário de Execução e Cadastro
        form_box = QGroupBox("Executar ou Salvar Script")
        grid = QGridLayout(form_box)
        grid.setSpacing(8)

        grid.addWidget(QLabel("Caminho do Script:"), 0, 0)
        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText("Selecione um arquivo .ps1, .bat, .cmd ou .py...")
        grid.addWidget(self.edit_path, 0, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_script)
        grid.addWidget(btn_browse, 0, 2)

        grid.addWidget(QLabel("Nome Amigável:"), 1, 0)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ex: Backup do Banco, Limpar Temporários...")
        grid.addWidget(self.edit_name, 1, 1, 1, 2)

        grid.addWidget(QLabel("Argumentos Opcionais:"), 2, 0)
        self.edit_args = QLineEdit()
        self.edit_args.setPlaceholderText("Ex: --verbose --force")
        grid.addWidget(self.edit_args, 2, 1, 1, 2)

        actions_row = QHBoxLayout()
        btn_save = QPushButton("Salvar no Catálogo")
        btn_save.clicked.connect(self._save_to_catalog)
        actions_row.addWidget(btn_save)

        actions_row.addStretch(1)

        self.btn_run = QPushButton("Executar Script Agora")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.setFixedWidth(160)
        self.btn_run.clicked.connect(lambda: self._execute_script(self.edit_path.text(), self.edit_args.text()))
        actions_row.addWidget(self.btn_run)

        self.btn_cancel = QPushButton("Cancelar Execução")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_script)
        actions_row.addWidget(self.btn_cancel)

        grid.addLayout(actions_row, 3, 0, 1, 3)
        root.addWidget(form_box)

        # 2. Catálogo de Scripts Salvos
        cat_box = QGroupBox("Scripts Salvos no Catálogo")
        cat_layout = QVBoxLayout(cat_box)
        cat_layout.setSpacing(6)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nome", "Caminho", "Argumentos", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 140)
        enable_sorting_on_table(self.table)
        cat_layout.addWidget(self.table)

        root.addWidget(cat_box, stretch=1)

        # 3. Painel de Log
        self.log_panel = LogPanelWidget()
        root.addWidget(self.log_panel, stretch=1)

    def _browse_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Script", "",
            "Scripts Compatíveis (*.ps1 *.bat *.cmd *.py *.vbs);;Todos os Arquivos (*.*)"
        )
        if path:
            self.edit_path.setText(path)
            if not self.edit_name.text():
                self.edit_name.setText(Path(path).stem)

    def _save_to_catalog(self) -> None:
        p = self.edit_path.text().strip()
        if not p or not Path(p).exists():
            show_toast(self, "O script selecionado não existe.")
            return

        name = self.edit_name.text().strip() or Path(p).stem
        args = self.edit_args.text().strip()

        add_or_update_script_entry(name, p, args)
        self._refresh_saved_scripts()
        show_toast(self, f"Script '{name}' salvo no catálogo!")

    def _refresh_saved_scripts(self) -> None:
        self._saved_scripts = load_saved_scripts()
        with batch_table_update(self.table):
            self.table.setRowCount(len(self._saved_scripts))

            for row, s in enumerate(self._saved_scripts):
                self.table.setItem(row, 0, SmartTableWidgetItem(s["name"], user_data=s))
                path_item = SmartTableWidgetItem(s["path"])
                path_item.setFont(QFont("Cascadia Mono", 9))
                self.table.setItem(row, 1, path_item)
                self.table.setItem(row, 2, SmartTableWidgetItem(s.get("args", "")))
                self.table.setItem(row, 3, SmartTableWidgetItem(""))

                # Painel de botões da linha
                cell_widget = QWidget()
                btn_layout = QHBoxLayout(cell_widget)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                btn_layout.setSpacing(4)

                btn_exec = QPushButton("Rodar")
                btn_exec.setStyleSheet("font-size: 10px; padding: 2px 8px;")
                btn_exec.clicked.connect(lambda checked=False, p=s["path"], a=s.get("args", ""): self._execute_script(p, a))
                btn_layout.addWidget(btn_exec)

                btn_del = QPushButton("Remover")
                btn_del.setStyleSheet("font-size: 10px; padding: 2px 6px;")
                btn_del.clicked.connect(lambda checked=False, p=s["path"]: self._remove_script(p))
                btn_layout.addWidget(btn_del)

                self.table.setCellWidget(row, 3, cell_widget)

    def _remove_script(self, script_path: str) -> None:
        delete_script_entry(script_path)
        self._refresh_saved_scripts()

    def _execute_script(self, script_path: str, args_str: str) -> None:
        p = Path(script_path.strip())
        if not p.is_file():
            show_toast(self, f"Arquivo não encontrado: {script_path}", duration_ms=2500)
            return

        cmd = build_script_command(str(p), args_str)

        self.log_panel.clear()
        self.log_panel.append_log(f"Iniciando execução: {p.name}")
        self.log_panel.append_log(f"Comando: {' '.join(cmd)}\n" + ("=" * 40))

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_process_output)
        self._process.finished.connect(self._on_process_finished)
        self._process.setWorkingDirectory(str(p.parent))

        prog = cmd[0]
        args = cmd[1:]
        self._process.start(prog, args)

        self.btn_run.setEnabled(False)
        self.btn_cancel.setVisible(True)

    def _on_process_output(self) -> None:
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self.log_panel.append_log(line)

    def _on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.btn_run.setEnabled(True)
        self.btn_cancel.setVisible(False)

        if exit_code == 0:
            self.log_panel.append_log("\n[SUCESSO] Script finalizado com êxito (código 0).")
            show_toast(self, "Script finalizado com sucesso!")
        else:
            self.log_panel.append_log(f"\n[FALHA] Processo encerrou com código de saída {exit_code}")
            show_toast(self, f"Execução encerrou com código {exit_code}", duration_ms=3000)

    def _cancel_script(self) -> None:
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.kill()
            self.log_panel.append_log("\n[CANCELADO] Execução interrompida pelo usuário.")
            self.btn_run.setEnabled(True)
            self.btn_cancel.setVisible(False)
