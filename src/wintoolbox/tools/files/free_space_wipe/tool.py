"""
Interface gráfica Fluent para o Sanitizador de Espaço Livre em Discos e Partições.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.files.free_space_wipe.logic import (
    build_cipher_wipe_command,
    get_drive_space_info,
)


@register
class FilesFreeSpaceWipeTool(Tool):
    id = "files.free_space_wipe"
    name = "Sanitizador de Espaço Livre"
    description = "Sobrescreve o espaço livre de discos e partições (via cipher /w) para prevenir a recuperação de arquivos deletados."
    category = "files"
    icon = "Shield"
    tags = ["wipe", "limpeza", "espaco livre", "cipher", "seguranca", "disco", "privacidade"]

    def __init__(self) -> None:
        super().__init__()
        self._process: Optional[QProcess] = None

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Seleção de Pasta / Drive
        top_form = QFormLayout()
        top_form.setSpacing(8)

        dir_row = QHBoxLayout()
        self.edit_path = QLineEdit("C:\\")
        btn_browse = QPushButton("Procurar Unidade / Pasta...")
        btn_refresh_info = QPushButton("Atualizar Dados")

        dir_row.addWidget(self.edit_path, 1)
        dir_row.addWidget(btn_browse)
        dir_row.addWidget(btn_refresh_info)
        top_form.addRow("Pasta ou Disco Alvo:", dir_row)

        self.combo_engine = QComboBox()
        self.combo_engine.addItem("Utilitário Oficial do Windows (cipher /w) — 3 Passadas Completas (0x00, 0xFF, Random)", "cipher")
        top_form.addRow("Método de Sanitização:", self.combo_engine)

        layout.addLayout(top_form)

        # Painel de Informações de Armazenamento
        self.lbl_disk_info = QLabel("Carregando informações de disco...")
        self.lbl_disk_info.setStyleSheet("font-weight: 600; color: #2e7d32; padding: 4px 0;")
        layout.addWidget(self.lbl_disk_info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Aviso de Segurança
        notice_box = QLabel(
            "⚠️ ATENÇÃO: Esta operação sobrescreve exclusivamente os setores NÃO alocados (espaço livre) "
            "do disco para garantir que arquivos já deletados não possam ser recuperados com softwares forenses. "
            "Seus arquivos e programas existentes NÃO serão afetados."
        )
        notice_box.setWordWrap(True)
        notice_box.setStyleSheet("background-color: rgba(255, 152, 0, 0.1); border-left: 4px solid #ff9800; padding: 8px;")
        layout.addWidget(notice_box)

        # Botão de Execução
        action_bar = QHBoxLayout()
        self.btn_wipe = QPushButton("Iniciar Sanitização de Espaço Livre")
        self.btn_wipe.setStyleSheet("font-weight: bold; background-color: #d32f2f; color: white; padding: 8px 16px;")
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)

        action_bar.addWidget(self.btn_wipe)
        action_bar.addWidget(self.btn_cancel)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        # Console de Saída
        self.text_output = QPlainTextEdit()
        self.text_output.setReadOnly(True)
        font = QFont("Consolas, Courier New, monospace", 9)
        self.text_output.setFont(font)
        layout.addWidget(self.text_output, 1)

        # Conexões
        btn_browse.clicked.connect(self._on_browse)
        btn_refresh_info.clicked.connect(self._update_disk_info)
        self.edit_path.textChanged.connect(self._update_disk_info)
        self.btn_wipe.clicked.connect(self._on_start_wipe)
        self.btn_cancel.clicked.connect(self._on_cancel)

        self._update_disk_info()
        return container

    def _on_browse(self) -> None:
        p = QFileDialog.getExistingDirectory(None, "Selecione a Pasta ou Drive")
        if p:
            self.edit_path.setText(p)

    def _update_disk_info(self) -> None:
        path = self.edit_path.text().strip()
        if not path or not Path(path).exists():
            self.lbl_disk_info.setText("Caminho inválido ou inacessível.")
            return

        try:
            info = get_drive_space_info(path)
            self.lbl_disk_info.setText(
                f"Disco: {info['path']} — Livre: {info['free_formatted']} de {info['total_formatted']} "
                f"({info['percent_free']}% livre | {info['used_formatted']} usado)"
            )
            used_pct = int(100 - info["percent_free"])
            self.progress_bar.setValue(used_pct)
        except Exception:
            self.lbl_disk_info.setText("Não foi possível ler as estatísticas de espaço.")

    def _on_start_wipe(self) -> None:
        path = self.edit_path.text().strip()
        if not path or not Path(path).exists():
            QMessageBox.warning(None, "Atenção", "Selecione uma pasta ou unidade válida.")
            return

        ans = QMessageBox.warning(
            None,
            "Confirmar Sanitização de Espaço Livre",
            f"Deseja iniciar a sanitização de espaço livre em:\n{path}\n\n"
            f"O processo irá preencher os setores não alocados para impedir recuperação de dados deletados. "
            f"A operação pode demorar dependendo da velocidade e capacidade do disco.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        cmd = build_cipher_wipe_command(path)
        self.text_output.clear()
        self.text_output.appendPlainText(f">> Executando: {' '.join(cmd)}\n")
        self.text_output.appendPlainText(">> Aguarde... O Windows está executando as passadas de sanitização.\n")

        self._process = QProcess()
        self._process.setProgram(cmd[0])
        self._process.setArguments(cmd[1:])
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        self.btn_wipe.setEnabled(False)
        self.btn_cancel.setEnabled(True)
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
        self.btn_wipe.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.text_output.appendPlainText(f"\n>> Processo finalizado com código {exit_code}.")
        if exit_code == 0:
            QMessageBox.information(None, "Concluído", "Sanitização de espaço livre concluída com sucesso.")
        else:
            QMessageBox.warning(None, "Finalizado", f"O processo terminou com código {exit_code}.")
        self._update_disk_info()

    def _on_cancel(self) -> None:
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.kill()
            self.text_output.appendPlainText("\n>> Operação cancelada pelo usuário.")
            self.btn_wipe.setEnabled(True)
            self.btn_cancel.setEnabled(False)
