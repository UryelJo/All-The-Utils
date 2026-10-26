"""
Ferramenta: Monitor de Pastas em Tempo Real (Folder Watcher).
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import (
    FolderWatchEvent,
    compute_snapshot_diff,
    format_events_as_csv,
    take_directory_snapshot,
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)


@register
class FolderWatcherTool(Tool):
    id = "files.folder_watcher"
    name = "Monitor de Pastas em Tempo Real"
    category = "Arquivos e Pastas"
    description = "Monitore pastas e receba alertas imediatos sobre arquivos criados, alterados ou deletados"
    keywords = ["monitor", "watcher", "pasta", "tempo real", "eventos", "alerta", "notificação", "arquivos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FolderWatcherView(self, parent)


class FolderWatcherView(QWidget):
    def __init__(self, tool: FolderWatcherTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.timer = QTimer(self)
        self.timer.setInterval(1500)  # 1.5s de intervalo
        self.timer.timeout.connect(self._check_folder)

        self.is_monitoring = False
        self.last_snapshot: Dict[Path, Tuple[float, int]] = {}
        self.events_history: List[FolderWatchEvent] = []
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

        # Card de Configuração
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QVBoxLayout(card)
        l_card.setSpacing(10)

        r_f = QHBoxLayout()
        r_f.addWidget(QLabel("Pasta a monitorar:"))
        self.txt_folder = QLineEdit(str(Path.home() / "Downloads"))
        r_f.addWidget(self.txt_folder, stretch=1)
        btn_browse = QPushButton("Selecionar Pasta...")
        btn_browse.clicked.connect(self._browse_folder)
        r_f.addWidget(btn_browse)
        l_card.addLayout(r_f)

        r_opts = QHBoxLayout()
        self.chk_recursive = QCheckBox("Monitorar subpastas (Recursivo)")
        self.chk_recursive.setChecked(True)
        r_opts.addWidget(self.chk_recursive)

        self.chk_notify = QCheckBox("Notificar na Área de Notificação (Tray)")
        self.chk_notify.setChecked(True)
        r_opts.addWidget(self.chk_notify)
        r_opts.addStretch()

        self.btn_toggle = QPushButton("Iniciar Monitoramento")
        self.btn_toggle.setProperty("class", "primary")
        self.btn_toggle.clicked.connect(self._toggle_monitoring)
        r_opts.addWidget(self.btn_toggle)
        l_card.addLayout(r_opts)

        layout.addWidget(card)

        # Status
        self.lbl_status = QLabel("Status: Parado. Clique em 'Iniciar Monitoramento'.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Tabela de Eventos
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Horário", "Evento", "Arquivo", "Caminho Completo", "Detalhes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table)

        # Botões de Ação
        r_acts = QHBoxLayout()
        btn_clear = QPushButton("Limpar Histórico")
        btn_clear.clicked.connect(self._clear_history)
        r_acts.addWidget(btn_clear)

        btn_export = QPushButton("Exportar Log (.CSV)...")
        btn_export.clicked.connect(self._export_csv)
        r_acts.addWidget(btn_export)

        btn_open = QPushButton("Abrir Pasta Monitorada")
        btn_open.clicked.connect(self._open_folder)
        r_acts.addWidget(btn_open)
        r_acts.addStretch()
        layout.addLayout(r_acts)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Monitorar", self.txt_folder.text())
        if f:
            self.txt_folder.setText(f)

    def _toggle_monitoring(self):
        if not self.is_monitoring:
            folder = Path(self.txt_folder.text().strip())
            if not folder.is_dir():
                QMessageBox.warning(self, "Aviso", "Selecione uma pasta válida existente para monitorar.")
                return

            self.is_monitoring = True
            self.txt_folder.setEnabled(False)
            self.chk_recursive.setEnabled(False)
            self.btn_toggle.setText("Parar Monitoramento")
            self.btn_toggle.setProperty("class", "secondary")
            self.btn_toggle.setStyleSheet("background-color: #d9534f; color: white;")
            self.lbl_status.setText(f"Status: Ativo e monitorando '{folder.name}' a cada 1.5s...")

            # Snapshot inicial
            self.last_snapshot = take_directory_snapshot(folder, recursive=self.chk_recursive.isChecked())
            self.timer.start()
        else:
            self.timer.stop()
            self.is_monitoring = False
            self.txt_folder.setEnabled(True)
            self.chk_recursive.setEnabled(True)
            self.btn_toggle.setText("Iniciar Monitoramento")
            self.btn_toggle.setProperty("class", "primary")
            self.btn_toggle.setStyleSheet("")
            self.lbl_status.setText("Status: Monitoramento pausado.")

    def _check_folder(self):
        if not self.is_monitoring:
            return

        folder = Path(self.txt_folder.text().strip())
        if not folder.is_dir():
            return

        rec = self.chk_recursive.isChecked()

        def worker(ctx):
            new_snap = take_directory_snapshot(folder, recursive=rec)
            evs = compute_snapshot_diff(self.last_snapshot, new_snap)
            return new_snap, evs

        def on_done(res):
            new_snap, new_events = res
            self.last_snapshot = new_snap

            if new_events:
                with batch_table_update(self.table):
                    for ev in new_events:
                        self.events_history.insert(0, ev)
                        row = 0
                        self.table.insertRow(row)
                        self.table.setItem(row, 0, SmartTableWidgetItem(ev.timestamp))

                        ev_item = SmartTableWidgetItem(ev.event_type)
                        if ev.event_type == "Criado":
                            ev_item.setForeground(Qt.darkGreen)
                        elif ev.event_type == "Modificado":
                            ev_item.setForeground(Qt.blue)
                        elif ev.event_type == "Excluído":
                            ev_item.setForeground(Qt.red)
                        self.table.setItem(row, 1, ev_item)

                        self.table.setItem(row, 2, SmartTableWidgetItem(ev.path.name, sort_value=ev.path.name.lower()))
                        self.table.setItem(row, 3, SmartTableWidgetItem(str(ev.path)))
                        self.table.setItem(row, 4, SmartTableWidgetItem(ev.details))

                self.lbl_status.setText(f"Status: Ativo | Último evento detectado às {new_events[0].timestamp} ({len(self.events_history)} total).")

        self.runner.start_task(worker, on_finished=on_done)

    def _clear_history(self):
        self.events_history.clear()
        self.table.setRowCount(0)
        self.lbl_status.setText("Histórico de eventos limpo.")

    def _export_csv(self):
        if not self.events_history:
            QMessageBox.information(self, "Exportar", "Não há eventos registrados para exportar.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Relatório CSV", "eventos_monitor.csv", "Arquivos CSV (*.csv)")
        if save_path:
            csv_text = format_events_as_csv(self.events_history)
            Path(save_path).write_text(csv_text, encoding="utf-8-sig")
            QMessageBox.information(self, "Sucesso", f"Relatório exportado com sucesso em:\n{save_path}")

    def _open_folder(self):
        folder = Path(self.txt_folder.text().strip())
        if folder.is_dir():
            os.startfile(str(folder))
