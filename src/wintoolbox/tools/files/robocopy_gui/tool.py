"""
Interface gráfica Fluent para o Assistente Robocopy do Windows.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.files.robocopy_gui.logic import (
    build_robocopy_command,
    parse_robocopy_exit_code,
)


@register
class FilesRobocopyGuiTool(Tool):
    id = "files.robocopy_gui"
    name = "Assistente Robocopy"
    description = "Interface visual para o Robocopy do Windows: espelhamento (/MIR), retomada (/Z), multithread (/MT) e simulação."
    category = "Arquivos e Pastas"
    icon = "Copy"
    tags = ["robocopy", "copia", "sincronizar", "espelho", "backup", "multithread"]

    def __init__(self) -> None:
        super().__init__()
        self._process: Optional[QProcess] = None

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Seleção de Pastas
        paths_form = QFormLayout()
        paths_form.setSpacing(8)

        # Origem
        orig_row = QHBoxLayout()
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Caminho da pasta de origem...")
        btn_browse_src = QPushButton("Procurar...")
        orig_row.addWidget(self.edit_source, 1)
        orig_row.addWidget(btn_browse_src)
        paths_form.addRow("Pasta de Origem:", orig_row)

        # Destino
        dst_row = QHBoxLayout()
        self.edit_target = QLineEdit()
        self.edit_target.setPlaceholderText("Caminho da pasta de destino...")
        btn_browse_dst = QPushButton("Procurar...")
        dst_row.addWidget(self.edit_target, 1)
        dst_row.addWidget(btn_browse_dst)
        paths_form.addRow("Pasta de Destino:", dst_row)

        layout.addLayout(paths_form)

        # Parâmetros e Opções
        opts_layout = QHBoxLayout()
        opts_layout.setSpacing(16)

        # Coluna 1: Modo e Threads
        col1 = QFormLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Espelhamento Completo (/MIR) - Cópia exata e limpa", "mirror")
        self.combo_mode.addItem("Copiar Todas as Subpastas (/E)", "all_subdirs")
        self.combo_mode.addItem("Copiar Apenas Arquivos Mais Novos (/XO /E)", "newer_only")
        col1.addRow("Modo de Cópia:", self.combo_mode)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 128)
        self.spin_threads.setValue(8)
        col1.addRow("Threads Paralelas (/MT):", self.spin_threads)
        opts_layout.addLayout(col1)

        # Coluna 2: Flags de Proteção
        col2 = QVBoxLayout()
        self.chk_dry_run = QCheckBox("Modo Simulação Apenas (/L - Dry Run sem gravar nada)")
        self.chk_dry_run.setChecked(True)
        self.chk_restartable = QCheckBox("Modo Retomável em caso de interrupção (/Z)")
        self.chk_restartable.setChecked(True)
        col2.addWidget(self.chk_dry_run)
        col2.addWidget(self.chk_restartable)
        opts_layout.addLayout(col2)

        layout.addLayout(opts_layout)

        # Exclusões de Pastas e Arquivos
        excl_layout = QHBoxLayout()
        excl_layout.setSpacing(10)

        excl_dirs_lay = QVBoxLayout()
        excl_dirs_lay.addWidget(QLabel("Excluir Pastas (/XD):"))
        self.edit_exclude_dirs = QLineEdit(".git node_modules __pycache__ .venv")
        excl_dirs_lay.addWidget(self.edit_exclude_dirs)
        excl_layout.addLayout(excl_dirs_lay)

        excl_files_lay = QVBoxLayout()
        excl_files_lay.addWidget(QLabel("Excluir Arquivos (/XF):"))
        self.edit_exclude_files = QLineEdit("*.tmp *.bak Thumbs.db")
        excl_files_lay.addWidget(self.edit_exclude_files)
        excl_layout.addLayout(excl_files_lay)

        layout.addLayout(excl_layout)

        # Linha de Comando Gerada
        cmd_box = QHBoxLayout()
        cmd_box.addWidget(QLabel("Comando Robocopy Gerado:"))
        self.lbl_cmd_preview = QLineEdit()
        self.lbl_cmd_preview.setReadOnly(True)
        btn_copy_cmd = QPushButton("Copiar Comando")
        cmd_box.addWidget(self.lbl_cmd_preview, 1)
        cmd_box.addWidget(btn_copy_cmd)
        layout.addLayout(cmd_box)

        # Botão de Execução
        exec_bar = QHBoxLayout()
        self.btn_run = QPushButton("Executar Robocopy")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.btn_stop = QPushButton("Interromper")
        self.btn_stop.setEnabled(False)

        exec_bar.addWidget(self.btn_run)
        exec_bar.addWidget(self.btn_stop)
        exec_bar.addStretch()
        layout.addLayout(exec_bar)

        # Console de Saída
        self.text_output = QPlainTextEdit()
        self.text_output.setReadOnly(True)
        font = QFont("Consolas, Courier New, monospace", 9)
        self.text_output.setFont(font)
        layout.addWidget(self.text_output, 1)

        # Conexões
        btn_browse_src.clicked.connect(self._on_browse_src)
        btn_browse_dst.clicked.connect(self._on_browse_dst)
        self.edit_source.textChanged.connect(self._update_cmd_preview)
        self.edit_target.textChanged.connect(self._update_cmd_preview)
        self.combo_mode.currentIndexChanged.connect(self._update_cmd_preview)
        self.spin_threads.valueChanged.connect(self._update_cmd_preview)
        self.chk_dry_run.toggled.connect(self._update_cmd_preview)
        self.chk_restartable.toggled.connect(self._update_cmd_preview)
        self.edit_exclude_dirs.textChanged.connect(self._update_cmd_preview)
        self.edit_exclude_files.textChanged.connect(self._update_cmd_preview)
        btn_copy_cmd.clicked.connect(self._on_copy_cmd)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop.clicked.connect(self._on_stop)

        self._update_cmd_preview()
        return container

    def _on_browse_src(self) -> None:
        p = QFileDialog.getExistingDirectory(None, "Selecione a Pasta de Origem")
        if p:
            self.edit_source.setText(p)

    def _on_browse_dst(self) -> None:
        p = QFileDialog.getExistingDirectory(None, "Selecione a Pasta de Destino")
        if p:
            self.edit_target.setText(p)

    def _get_command_args(self) -> list[str]:
        src = self.edit_source.text().strip() or "C:\\Origem"
        dst = self.edit_target.text().strip() or "D:\\Destino"
        mode = self.combo_mode.currentData() or "mirror"
        threads = self.spin_threads.value()
        dry_run = self.chk_dry_run.isChecked()
        restartable = self.chk_restartable.isChecked()
        xd = self.edit_exclude_dirs.text().split()
        xf = self.edit_exclude_files.text().split()

        return build_robocopy_command(
            src, dst,
            mode=mode,
            threads=threads,
            dry_run=dry_run,
            restartable=restartable,
            exclude_dirs=xd,
            exclude_files=xf,
        )

    def _update_cmd_preview(self) -> None:
        cmd = self._get_command_args()
        self.lbl_cmd_preview.setText(" ".join(cmd))

    def _on_copy_cmd(self) -> None:
        cmd_text = self.lbl_cmd_preview.text()
        if cmd_text:
            QApplication.clipboard().setText(cmd_text)

    def _on_run(self) -> None:
        src = self.edit_source.text().strip()
        dst = self.edit_target.text().strip()
        if not src or not dst:
            QMessageBox.warning(None, "Atenção", "Preencha a pasta de origem e a pasta de destino.")
            return

        cmd = self._get_command_args()
        self.text_output.clear()
        self.text_output.appendPlainText(f">> Executando: {' '.join(cmd)}\n")

        self._process = QProcess()
        self._process.setProgram(cmd[0])
        self._process.setArguments(cmd[1:])
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._process.start()

    def _on_stdout(self) -> None:
        if self._process:
            data = self._process.readAllStandardOutput().data().decode("cp850", errors="replace")
            self.text_output.appendPlainText(data)

    def _on_stderr(self) -> None:
        if self._process:
            data = self._process.readAllStandardError().data().decode("cp850", errors="replace")
            self.text_output.appendPlainText(data)

    def _on_finished(self, exit_code: int) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        res = parse_robocopy_exit_code(exit_code)
        self.text_output.appendPlainText(f"\n>> Finalizado com código de saída {exit_code}: {res['summary']}")
        for d in res["details"]:
            self.text_output.appendPlainText(f"   - {d}")

    def _on_stop(self) -> None:
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.kill()
            self.text_output.appendPlainText("\n>> Processo interrompido pelo usuário.")
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
