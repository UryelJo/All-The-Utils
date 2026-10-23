"""
Ferramenta: Backup e Exportação de Drivers do Windows.
Listagem de drivers de terceiros e exportação completa em lote via pnputil.
"""
import os
from pathlib import Path
import subprocess
from typing import Optional
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.system.driver_backup.logic import (
    export_drivers_to_folder, list_third_party_drivers
)


@register
class DriverBackupTool(Tool):
    id = "system.driver_backup"
    name = "Backup de Drivers do Windows"
    category = "Sistema"
    description = "Exportação e backup completo de drivers de terceiros instalados (DISM / pnputil)"
    keywords = ["driver", "drivers", "backup", "pnputil", "inf", "hardware", "dispositivos", "exportar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DriverBackupView(self, parent)


class DriverBackupView(QWidget):
    def __init__(self, tool: DriverBackupTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._drivers = []
        self._build_ui()
        self._refresh_drivers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._refresh_drivers)
        top_bar.addWidget(self.btn_refresh)

        top_bar.addStretch()

        self.lbl_count = QLabel("0 drivers instalados")
        self.lbl_count.setStyleSheet("color: #888890; font-weight: 500;")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "INF Publicado", "Provedor / Fabricante", "Classe do Dispositivo", "Versão", "Data do Driver"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Barra de Destino e Exportação
        export_box = QHBoxLayout()
        export_box.setSpacing(8)

        export_box.addWidget(QLabel("Pasta de Destino do Backup:"))
        self.txt_dest = QLineEdit()
        default_dir = str(Path.home() / "Desktop" / "Backup_Drivers")
        self.txt_dest.setText(default_dir)
        export_box.addWidget(self.txt_dest, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_dest)
        export_box.addWidget(btn_browse)

        self.btn_export = QPushButton("Exportar Todos os Drivers")
        self.btn_export.setProperty("class", "primary")
        self.btn_export.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_export.clicked.connect(self._on_export)
        export_box.addWidget(self.btn_export)

        layout.addLayout(export_box)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

    def _refresh_drivers(self):
        self._drivers = list_third_party_drivers()
        self.table.setRowCount(len(self._drivers))

        for row, d in enumerate(self._drivers):
            self.table.setItem(row, 0, QTableWidgetItem(d.get("published_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(d.get("provider", "")))
            self.table.setItem(row, 2, QTableWidgetItem(d.get("class_name", "")))
            self.table.setItem(row, 3, QTableWidgetItem(d.get("version", "")))
            self.table.setItem(row, 4, QTableWidgetItem(d.get("date", "")))

        self.lbl_count.setText(f"{len(self._drivers)} pacotes de drivers de terceiros")

    def _on_browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Backup de Drivers")
        if d:
            self.txt_dest.setText(d)

    def _on_export(self):
        dest_str = self.txt_dest.text().strip()
        if not dest_str:
            QMessageBox.warning(self, "Aviso", "Informe a pasta de destino para o backup.")
            return

        dest_path = Path(dest_str)
        self.btn_export.setEnabled(False)
        self.lbl_status.setText("Exportando drivers do sistema (isso pode levar alguns minutos)...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Invocando pnputil para exportação de drivers...")
            ok, msg, count = export_drivers_to_folder(dest_path)
            ctx.progress(100, 100, "Concluído!")
            return ok, msg, count

        def _done(result, exc):
            self.btn_export.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha na exportação: {exc}")
                return

            ok, msg, count = result
            if ok:
                self.lbl_status.setText("Backup concluído com sucesso!")
                ans = QMessageBox.question(
                    self,
                    "Backup Concluído",
                    f"{msg}\n\nDeseja abrir a pasta onde os drivers foram salvos?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes and dest_path.exists():
                    subprocess.Popen(f'explorer "{dest_path}"')
            else:
                self.lbl_status.setText("Erro na exportação.")
                if not is_admin():
                    ans = QMessageBox.question(
                        self,
                        "Privilégios Necessários",
                        f"{msg}\n\nPara exportar drivers é recomendável privilégio de Administrador. Deseja reiniciar como Administrador?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if ans == QMessageBox.Yes:
                        request_elevation()
                else:
                    QMessageBox.critical(self, "Erro", msg)

        def _on_prog(cur, tot, msg):
            if msg:
                self.lbl_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)
