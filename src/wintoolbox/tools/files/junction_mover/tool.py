"""
Interface gráfica da ferramenta Mover Pasta com Junção NTFS.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.files.junction_mover.logic import (
    calculate_dir_size, get_drive_free_space, is_reparse_point,
    move_folder_and_create_junction, validate_move_junction,
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("files.junction_mover.ui")


@register
class JunctionMoverTool(Tool):
    id = "files.junction_mover"
    name = "Mover Pasta com Junção NTFS"
    category = "Arquivos e Pastas"
    description = "Mova pastas pesadas para outro disco ou partição liberando espaço e mantendo o acesso transparente via Junção NTFS"
    keywords = ["junction", "juncao", "mover", "disco", "ssd", "espaco", "mklink", "link", "ntfs", "pastas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return JunctionMoverView(self, parent)


class JunctionMoverView(QWidget):
    def __init__(self, tool: JunctionMoverTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._is_running = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(12)

        # 1. Pasta de Origem
        grid.addWidget(QLabel("Pasta de Origem (que será movida):"), 0, 0)
        self.txt_source = QLineEdit()
        self.txt_source.setPlaceholderText("Ex: C:\\Users\\SeuUsuario\\AppData\\Local\\PastasPesadas")
        self.txt_source.textChanged.connect(self._on_source_changed)
        grid.addWidget(self.txt_source, 0, 1)

        btn_browse_src = QPushButton("Procurar...")
        btn_browse_src.clicked.connect(self._browse_source)
        grid.addWidget(btn_browse_src, 0, 2)

        self.lbl_src_info = QLabel("Selecione a pasta para verificar o tamanho.")
        self.lbl_src_info.setStyleSheet("color: #888888; font-size: 12px;")
        grid.addWidget(self.lbl_src_info, 1, 1, 1, 2)

        # 2. Pasta de Destino
        grid.addWidget(QLabel("Pasta de Destino (em outro disco/partição):"), 2, 0)
        self.txt_target = QLineEdit()
        self.txt_target.setPlaceholderText("Ex: D:\\ArmazenamentoSecundario\\PastasPesadas")
        self.txt_target.textChanged.connect(self._on_target_changed)
        grid.addWidget(self.txt_target, 2, 1)

        btn_browse_tgt = QPushButton("Procurar...")
        btn_browse_tgt.clicked.connect(self._browse_target)
        grid.addWidget(btn_browse_tgt, 2, 2)

        self.lbl_tgt_info = QLabel("Selecione o destino para verificar o espaço livre disponível.")
        self.lbl_tgt_info.setStyleSheet("color: #888888; font-size: 12px;")
        grid.addWidget(self.lbl_tgt_info, 3, 1, 1, 2)

        layout.addWidget(card)

        # Barra de Ação
        action_box = QFrame()
        action_box.setObjectName("Card")
        a_lay = QVBoxLayout(action_box)
        a_lay.setContentsMargins(16, 14, 16, 14)
        a_lay.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        a_lay.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Pronto para mover arquivos e criar junção.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 12px;")
        a_lay.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_move = QPushButton("Mover Pasta e Criar Junção")
        self.btn_move.setProperty("class", "accent")
        self.btn_move.setStyleSheet("padding: 8px 18px; font-weight: 600;")
        self.btn_move.clicked.connect(self._on_execute_click)
        btn_row.addWidget(self.btn_move)

        a_lay.addLayout(btn_row)
        layout.addWidget(action_box)
        layout.addStretch()

    def _browse_source(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Origem")
        if d:
            self.txt_source.setText(d)

    def _browse_target(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta ou Disco de Destino")
        if d:
            src_name = Path(self.txt_source.text().strip()).name if self.txt_source.text().strip() else "NovaPasta"
            suggested = Path(d) / src_name
            self.txt_target.setText(str(suggested))

    def _on_source_changed(self) -> None:
        txt = self.txt_source.text().strip()
        if not txt:
            self.lbl_src_info.setText("Selecione a pasta para verificar o tamanho.")
            return
        p = Path(txt)
        if not p.exists() or not p.is_dir():
            self.lbl_src_info.setText("Pasta inexistente ou inválida.")
            return
        if is_reparse_point(p):
            self.lbl_src_info.setText("Aviso: Esta pasta já é uma junção NTFS ou link simbólico!")
            return
        b, count = calculate_dir_size(p)
        mb = round(b / (1024 * 1024), 2)
        gb = round(b / (1024 * 1024 * 1024), 2)
        txt_size = f"{gb} GB" if gb >= 1.0 else f"{mb} MB"
        self.lbl_src_info.setText(f"Tamanho total: {txt_size} ({count:,} arquivo(s)).")

    def _on_target_changed(self) -> None:
        txt = self.txt_target.text().strip()
        if not txt:
            self.lbl_tgt_info.setText("Selecione o destino para verificar o espaço livre disponível.")
            return
        p = Path(txt)
        free_b = get_drive_free_space(p.parent if not p.exists() else p)
        gb = round(free_b / (1024 * 1024 * 1024), 2)
        self.lbl_tgt_info.setText(f"Espaço livre no disco de destino: {gb} GB disponíveis.")

    def _on_execute_click(self) -> None:
        if self._is_running:
            return

        s_str = self.txt_source.text().strip()
        t_str = self.txt_target.text().strip()

        if not s_str or not t_str:
            show_toast(self, "Preencha os caminhos de origem e destino.", kind="error")
            return

        src = Path(s_str)
        tgt = Path(t_str)

        is_valid, validation_msg = validate_move_junction(src, tgt)
        if not is_valid:
            show_toast(self, validation_msg, kind="error")
            QMessageBox.warning(self, "Aviso de Validação", validation_msg)
            return

        if src.drive.upper() == tgt.drive.upper():
            ret = QMessageBox.question(
                self,
                "Mesmo Disco Físico",
                f"A origem e o destino estão no mesmo disco ({src.drive}).\n"
                "Junções NTFS são mais úteis para mover arquivos para OUTRO disco e liberar espaço na partição do sistema.\n\n"
                "Deseja continuar mesmo assim?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                return

        reply = QMessageBox.warning(
            self,
            "Confirmar Criação de Junção NTFS",
            f"A pasta original:\n{src}\n\nserá copiada para:\n{tgt}\n\n"
            "Após a cópia segura, a pasta original será substituída por uma Junção NTFS "
            "que redirecionará qualquer acesso de forma transparente.\n\n"
            "Deseja prosseguir?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._is_running = True
        self.btn_move.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Iniciando transferência...")

        def _worker():
            def _cb(pct: int, msg: str):
                self.progress_bar.setValue(pct)
                self.lbl_status.setText(msg)
            return move_folder_and_create_junction(src, tgt, progress_cb=_cb)

        def _on_done(res):
            self._is_running = False
            self.btn_move.setEnabled(True)
            self.progress_bar.setValue(100)
            self.lbl_status.setText("Pasta movida e Junção NTFS criada com sucesso!")
            show_toast(self, "Junção NTFS criada com sucesso!", kind="success")
            QMessageBox.information(
                self,
                "Operação Concluída",
                f"A pasta foi movida com sucesso!\n\n"
                f"Origem (Junção): {res['source']}\n"
                f"Destino Real: {res['target']}\n"
                f"Arquivos transferidos: {res['total_files']:,}"
            )

        def _on_error(err):
            self._is_running = False
            self.btn_move.setEnabled(True)
            self.lbl_status.setText(f"Erro: {err}")
            show_toast(self, f"Erro: {err}", kind="error")

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
