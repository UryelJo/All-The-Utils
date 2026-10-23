"""
Ferramenta: Modificador em Lote de Datas e Atributos de Arquivos (Timestamp Editor).
"""
from datetime import datetime
from pathlib import Path
import time
from typing import List, Optional
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import (
    FileTimestampInfo,
    batch_update_timestamps,
    get_file_timestamps,
)


@register
class TimestampEditorTool(Tool):
    id = "files.timestamp_editor"
    name = "Modificador de Datas de Arquivos (Timestamp)"
    category = "Arquivos e Pastas"
    description = "Altere em lote datas de criação (ctime), modificação (mtime) e acesso (atime) de arquivos"
    keywords = ["timestamp", "data", "hora", "ctime", "mtime", "atime", "metadados", "arquivos", "modificar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TimestampEditorView(self, parent)


class TimestampEditorView(QWidget):
    def __init__(self, tool: TimestampEditorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.file_items: List[FileTimestampInfo] = []
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

        # Botões de Entrada
        r_in = QHBoxLayout()
        btn_add_files = QPushButton("Adicionar Arquivos...")
        btn_add_files.clicked.connect(self._add_files)
        r_in.addWidget(btn_add_files)

        btn_add_folder = QPushButton("Adicionar Pasta Inteira...")
        btn_add_folder.clicked.connect(self._add_folder)
        r_in.addWidget(btn_add_folder)

        btn_clear = QPushButton("Limpar Lista")
        btn_clear.clicked.connect(self._clear_list)
        r_in.addWidget(btn_clear)
        r_in.addStretch()
        layout.addLayout(r_in)

        # Tabela de Arquivos
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Arquivo", "Criação Atual", "Modificação Atual", "Último Acesso", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(220)
        layout.addWidget(self.table)

        # Card de Configuração das Novas Datas
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QVBoxLayout(card)
        l_card.setSpacing(10)

        lbl_sec = QLabel("Definição das Novas Datas:")
        lbl_sec.setStyleSheet("font-weight: 600;")
        l_card.addWidget(lbl_sec)

        # Linha de Checkboxes
        r_chk = QHBoxLayout()
        self.chk_ctime = QCheckBox("Alterar Data de Criação (Creation Time)")
        self.chk_ctime.setChecked(True)
        r_chk.addWidget(self.chk_ctime)

        self.chk_mtime = QCheckBox("Alterar Data de Modificação (Last Write Time)")
        self.chk_mtime.setChecked(True)
        r_chk.addWidget(self.chk_mtime)

        self.chk_atime = QCheckBox("Alterar Data de Último Acesso (Last Access Time)")
        self.chk_atime.setChecked(False)
        r_chk.addWidget(self.chk_atime)
        r_chk.addStretch()
        l_card.addLayout(r_chk)

        # Modo de Aplicação
        r_mode = QHBoxLayout()
        r_mode.addWidget(QLabel("Modo:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Data e Hora Específica Fixa", "fixed")
        self.cmb_mode.addItem("Definir para o Momento Atual (Agora)", "now")
        self.cmb_mode.addItem("Deslocar Horas Relativamente (+/- Horas)", "offset")
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        r_mode.addWidget(self.cmb_mode)

        self.dt_picker = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_picker.setCalendarPopup(True)
        self.dt_picker.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        r_mode.addWidget(self.dt_picker)

        self.lbl_offset = QLabel("Horas a somar (+/-):")
        self.lbl_offset.setVisible(False)
        r_mode.addWidget(self.lbl_offset)

        self.spin_offset_hours = QSpinBox()
        self.spin_offset_hours.setRange(-87600, 87600)
        self.spin_offset_hours.setValue(0)
        self.spin_offset_hours.setSuffix(" horas")
        self.spin_offset_hours.setVisible(False)
        r_mode.addWidget(self.spin_offset_hours)

        r_mode.addStretch()
        l_card.addLayout(r_mode)

        # Botão de Execução
        r_btn = QHBoxLayout()
        self.btn_apply = QPushButton("Aplicar Novas Datas aos Arquivos")
        self.btn_apply.setProperty("class", "primary")
        self.btn_apply.clicked.connect(self._apply_timestamps)
        r_btn.addWidget(self.btn_apply)
        r_btn.addStretch()
        l_card.addLayout(r_btn)

        layout.addWidget(card)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Adicione os arquivos desejados para alterar as datas.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _on_mode_changed(self, idx: int):
        mode = self.cmb_mode.currentData()
        self.dt_picker.setVisible(mode == "fixed")
        self.lbl_offset.setVisible(mode == "offset")
        self.spin_offset_hours.setVisible(mode == "offset")

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos")
        if files:
            for f in files:
                p = Path(f)
                if p.is_file():
                    try:
                        info = get_file_timestamps(p)
                        self.file_items.append(info)
                    except Exception:
                        pass
            self._refresh_table()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            for p in Path(folder).glob("*"):
                if p.is_file():
                    try:
                        info = get_file_timestamps(p)
                        self.file_items.append(info)
                    except Exception:
                        pass
            self._refresh_table()

    def _clear_list(self):
        self.file_items.clear()
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self.file_items))
        for row, item in enumerate(self.file_items):
            self.table.setItem(row, 0, QTableWidgetItem(item.path.name))
            self.table.setItem(row, 1, QTableWidgetItem(item.formatted_ctime))
            self.table.setItem(row, 2, QTableWidgetItem(item.formatted_mtime))
            self.table.setItem(row, 3, QTableWidgetItem(item.formatted_atime))
            self.table.setItem(row, 4, QTableWidgetItem("Pendente"))
        self.lbl_status.setText(f"{len(self.file_items)} arquivo(s) na lista prontos para alteração.")

    def _apply_timestamps(self):
        if not self.file_items:
            QMessageBox.warning(self, "Aviso", "Adicione ao menos um arquivo à lista.")
            return

        do_ctime = self.chk_ctime.isChecked()
        do_mtime = self.chk_mtime.isChecked()
        do_atime = self.chk_atime.isChecked()

        if not (do_ctime or do_mtime or do_atime):
            QMessageBox.warning(self, "Aviso", "Marque ao menos um atributo para alterar (Criação, Modificação ou Acesso).")
            return

        mode = self.cmb_mode.currentData()
        target_ts: Optional[float] = None
        offset_sec: Optional[float] = None

        if mode == "fixed":
            qdt = self.dt_picker.dateTime()
            target_ts = qdt.toSecsSinceEpoch()
        elif mode == "now":
            target_ts = time.time()
        elif mode == "offset":
            hours = self.spin_offset_hours.value()
            offset_sec = hours * 3600.0

        c_val = target_ts if do_ctime else None
        m_val = target_ts if do_mtime else None
        a_val = target_ts if do_atime else None

        paths = [item.path for item in self.file_items]
        self.btn_apply.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.lbl_status.setText("Atualizando datas dos arquivos...")

        def worker(ctx):
            return batch_update_timestamps(
                files=paths,
                ctime=c_val,
                mtime=m_val,
                atime=a_val,
                offset_seconds=offset_sec,
            )

        def on_done(results):
            self.btn_apply.setEnabled(True)
            self.prog_bar.setVisible(False)
            succ = sum(1 for r in results if r.success)
            fail = len(results) - succ

            for row, res in enumerate(results):
                status_item = QTableWidgetItem("Atualizado" if res.success else f"Erro: {res.error}")
                if res.success:
                    status_item.setForeground(Qt.darkGreen)
                    # Recarrega as datas atualizadas
                    try:
                        upd = get_file_timestamps(res.path)
                        self.file_items[row] = upd
                        self.table.setItem(row, 1, QTableWidgetItem(upd.formatted_ctime))
                        self.table.setItem(row, 2, QTableWidgetItem(upd.formatted_mtime))
                        self.table.setItem(row, 3, QTableWidgetItem(upd.formatted_atime))
                    except Exception:
                        pass
                else:
                    status_item.setForeground(Qt.red)
                self.table.setItem(row, 4, status_item)

            self.lbl_status.setText(f"Concluído! {succ} arquivo(s) atualizados com sucesso. Falhas: {fail}.")
            QMessageBox.information(
                self,
                "Operação Concluída",
                f"Datas atualizadas com sucesso!\n\nAtualizados: {succ}\nFalhas: {fail}"
            )

        self.runner.start_task(worker, on_finished=on_done)
