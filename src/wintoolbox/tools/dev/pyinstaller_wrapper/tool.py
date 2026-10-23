"""
Interface gráfica da ferramenta Gerador de Executáveis PyInstaller.
"""
from pathlib import Path
import sys
from typing import List, Optional
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.pyinstaller_wrapper.logic import (
    build_batch_script, build_pyinstaller_command, check_pyinstaller_available,
    validate_compilation_inputs
)
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("dev.pyinstaller_wrapper.ui")


@register
class PyInstallerWrapperTool(Tool):
    id = "dev.pyinstaller_wrapper"
    name = "Gerador de Executáveis"
    category = "Desenvolvimento"
    description = "Configuração e compilação de scripts Python em executáveis .exe nativos via PyInstaller com logs em tempo real"
    keywords = ["pyinstaller", "exe", "executavel", "build", "compilador", "python", "deploy", "dist", "dev"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PyInstallerWrapperView(self, parent)


class PyInstallerWrapperView(QWidget):
    def __init__(self, tool: PyInstallerWrapperTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._process: Optional[QProcess] = None

        self._build_ui()
        self._check_environment()
        self._update_command_preview()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Gerador de Executáveis (PyInstaller)",
            "Configuração visual e empacotamento de aplicações Python em binários (.exe) independentes para Windows."
        ))

        # Status do PyInstaller
        self.lbl_status = QLabel("Verificando ambiente...")
        self.lbl_status.setStyleSheet("padding: 4px 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.05); font-size: 11px;")
        root.addWidget(self.lbl_status)

        # 1. Arquivos e Nomes
        files_box = QGroupBox("Arquivos e Pastas do Projeto")
        grid_files = QGridLayout(files_box)
        grid_files.setSpacing(8)

        # Script principal
        grid_files.addWidget(QLabel("Script Principal (.py):"), 0, 0)
        self.edit_script = QLineEdit()
        self.edit_script.setPlaceholderText("Ex: C:/Projetos/MeuApp/main.py")
        self.edit_script.textChanged.connect(self._update_command_preview)
        grid_files.addWidget(self.edit_script, 0, 1)

        btn_browse_script = QPushButton("Procurar...")
        btn_browse_script.clicked.connect(self._browse_script)
        grid_files.addWidget(btn_browse_script, 0, 2)

        # Nome do Executável
        grid_files.addWidget(QLabel("Nome do Executável (.exe):"), 1, 0)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Deixe em branco para usar o nome do arquivo")
        self.edit_name.textChanged.connect(self._update_command_preview)
        grid_files.addWidget(self.edit_name, 1, 1, 1, 2)

        # Ícone .ico
        grid_files.addWidget(QLabel("Ícone (.ico):"), 2, 0)
        self.edit_icon = QLineEdit()
        self.edit_icon.setPlaceholderText("Opcional: C:/Projetos/MeuApp/assets/app.ico")
        self.edit_icon.textChanged.connect(self._update_command_preview)
        grid_files.addWidget(self.edit_icon, 2, 1)

        btn_browse_icon = QPushButton("Procurar...")
        btn_browse_icon.clicked.connect(self._browse_icon)
        grid_files.addWidget(btn_browse_icon, 2, 2)

        # Pasta de Saída (dist)
        grid_files.addWidget(QLabel("Pasta de Saída (Dist):"), 3, 0)
        self.edit_dist = QLineEdit()
        self.edit_dist.setPlaceholderText("Padrão: ./dist")
        self.edit_dist.textChanged.connect(self._update_command_preview)
        grid_files.addWidget(self.edit_dist, 3, 1)

        btn_browse_dist = QPushButton("Procurar...")
        btn_browse_dist.clicked.connect(self._browse_dist)
        grid_files.addWidget(btn_browse_dist, 3, 2)

        root.addWidget(files_box)

        # 2. Opções de Empacotamento
        opts_box = QGroupBox("Opções de Compilação")
        opts_layout = QGridLayout(opts_box)
        opts_layout.setSpacing(10)

        # Modo (Onefile vs Onedir)
        opts_layout.addWidget(QLabel("Estrutura do Binário:"), 0, 0)
        self.radio_onefile = QRadioButton("Arquivo Único (--onefile / .exe standalone)")
        self.radio_onefile.setChecked(True)
        self.radio_onefile.toggled.connect(self._update_command_preview)
        self.radio_onedir = QRadioButton("Pasta com DLLs (--onedir / inicialização rápida)")
        self.radio_onedir.toggled.connect(self._update_command_preview)
        mode_box = QHBoxLayout()
        mode_box.addWidget(self.radio_onefile)
        mode_box.addWidget(self.radio_onedir)
        mode_box.addStretch(1)
        opts_layout.addLayout(mode_box, 0, 1)

        # Janela / Console
        opts_layout.addWidget(QLabel("Interface Gráfica:"), 1, 0)
        self.switch_windowed = ToggleSwitch()
        self.switch_windowed.setChecked(True)
        self.switch_windowed.toggled.connect(self._update_command_preview)
        lbl_win_desc = QLabel("Ocultar janela preta de console (--windowed / --noconsole)")
        win_box = QHBoxLayout()
        win_box.addWidget(self.switch_windowed)
        win_box.addWidget(lbl_win_desc)
        win_box.addStretch(1)
        opts_layout.addLayout(win_box, 1, 1)

        # Imports Ocultos
        opts_layout.addWidget(QLabel("Imports Ocultos:"), 2, 0)
        self.edit_hidden = QLineEdit()
        self.edit_hidden.setPlaceholderText("Módulos extras separados por vírgula (ex: pkg_resources, PIL.Image)")
        self.edit_hidden.textChanged.connect(self._update_command_preview)
        opts_layout.addWidget(self.edit_hidden, 2, 1)

        # Add Data
        opts_layout.addWidget(QLabel("Arquivos Adicionais:"), 3, 0)
        self.edit_add_data = QLineEdit()
        self.edit_add_data.setPlaceholderText("Formato origem;destino (ex: assets;assets, config.json;.)")
        self.edit_add_data.textChanged.connect(self._update_command_preview)
        opts_layout.addWidget(self.edit_add_data, 3, 1)

        root.addWidget(opts_box)

        # 3. Prévia do Comando e Ações
        cmd_box = QGroupBox("Comando Gerado")
        cmd_layout = QVBoxLayout(cmd_box)
        cmd_layout.setSpacing(8)

        self.edit_cmd = QLineEdit()
        self.edit_cmd.setReadOnly(True)
        self.edit_cmd.setFont(QFont("Cascadia Mono", 9))
        cmd_layout.addWidget(self.edit_cmd)

        actions_row = QHBoxLayout()
        btn_copy_cmd = QPushButton("Copiar Comando")
        btn_copy_cmd.clicked.connect(self._copy_command)
        actions_row.addWidget(btn_copy_cmd)

        btn_save_bat = QPushButton("Salvar Arquivo .bat")
        btn_save_bat.clicked.connect(self._save_bat)
        actions_row.addWidget(btn_save_bat)

        actions_row.addStretch(1)

        self.btn_compile = QPushButton("Compilar Agora")
        self.btn_compile.setProperty("class", "primary")
        self.btn_compile.setFixedWidth(140)
        self.btn_compile.clicked.connect(self._start_compilation)
        actions_row.addWidget(self.btn_compile)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_compilation)
        actions_row.addWidget(self.btn_cancel)

        cmd_layout.addLayout(actions_row)
        root.addWidget(cmd_box)

        # 4. Painel de Log em Tempo Real
        self.log_panel = LogPanelWidget()
        root.addWidget(self.log_panel, stretch=1)

    def _check_environment(self) -> None:
        ok, msg = check_pyinstaller_available()
        color = "#10B981" if ok else "#EF4444"
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(f"padding: 4px 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.05); color: {color}; font-size: 11px;")
        if not ok:
            self.btn_compile.setEnabled(False)

    def _get_current_cmd_args(self) -> List[str]:
        script = self.edit_script.text().strip() or "main.py"
        name = self.edit_name.text().strip() or None
        icon = self.edit_icon.text().strip() or None
        dist = self.edit_dist.text().strip() or None
        onefile = self.radio_onefile.isChecked()
        windowed = self.switch_windowed.isChecked()

        hidden = [x.strip() for x in self.edit_hidden.text().split(",") if x.strip()]
        add_data = [x.strip() for x in self.edit_add_data.text().split(",") if x.strip()]

        return build_pyinstaller_command(
            script_path=script,
            app_name=name,
            onefile=onefile,
            windowed=windowed,
            icon_path=icon,
            add_data=add_data,
            hidden_imports=hidden,
            clean=True,
            dist_dir=dist
        )

    def _update_command_preview(self) -> None:
        cmd_args = self._get_current_cmd_args()
        formatted = []
        for a in cmd_args:
            if " " in a and not a.startswith('"'):
                formatted.append(f'"{a}"')
            else:
                formatted.append(a)
        self.edit_cmd.setText(" ".join(formatted))

    def _browse_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Script Python", "", "Arquivos Python (*.py *.pyw)")
        if path:
            self.edit_script.setText(path)
            if not self.edit_name.text():
                self.edit_name.setText(Path(path).stem)

    def _browse_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Ícone", "", "Ícones Windows (*.ico)")
        if path:
            self.edit_icon.setText(path)

    def _browse_dist(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Saída")
        if path:
            self.edit_dist.setText(path)

    def _copy_command(self) -> None:
        cmd = self.edit_cmd.text()
        if cmd:
            QApplication.clipboard().setText(cmd)
            show_toast(self, "Comando copiado para a área de transferência!")

    def _save_bat(self) -> None:
        cmd_args = self._get_current_cmd_args()
        script_dir = str(Path(self.edit_script.text().strip()).parent) if self.edit_script.text().strip() else None
        bat_content = build_batch_script(cmd_args, project_dir=script_dir)

        path, _ = QFileDialog.getSaveFileName(self, "Salvar Script de Compilação", "compilar.bat", "Script Batch (*.bat)")
        if path:
            Path(path).write_text(bat_content, encoding="utf-8")
            show_toast(self, f"Arquivo salvo com sucesso em: {Path(path).name}")

    def _start_compilation(self) -> None:
        script = self.edit_script.text().strip()
        icon = self.edit_icon.text().strip() or None

        errors = validate_compilation_inputs(script, icon)
        if errors:
            show_toast(self, errors[0], duration_ms=3000)
            return

        cmd_args = self._get_current_cmd_args()
        self.log_panel.clear()
        self.log_panel.append_log("Iniciando compilação PyInstaller...")
        self.log_panel.append_log(f"Comando: {' '.join(cmd_args)}\n")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_process_output)
        self._process.finished.connect(self._on_process_finished)

        work_dir = str(Path(script).parent)
        self._process.setWorkingDirectory(work_dir)

        prog = cmd_args[0]
        args = cmd_args[1:]
        self._process.start(prog, args)

        self.btn_compile.setEnabled(False)
        self.btn_cancel.setVisible(True)

    def _on_process_output(self) -> None:
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self.log_panel.append_log(line)

    def _on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.btn_compile.setEnabled(True)
        self.btn_cancel.setVisible(False)

        if exit_code == 0:
            self.log_panel.append_log("\n[SUCESSO] Compilação finalizada com êxito!")
            show_toast(self, "Executável gerado com sucesso!")
        else:
            self.log_panel.append_log(f"\n[FALHA] Processo encerrou com código de erro {exit_code}")
            show_toast(self, f"A compilação falhou (código {exit_code})", duration_ms=3000)

    def _cancel_compilation(self) -> None:
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.kill()
            self.log_panel.append_log("\n[CANCELADO] Processo interrompido pelo usuário.")
            self.btn_compile.setEnabled(True)
            self.btn_cancel.setVisible(False)
