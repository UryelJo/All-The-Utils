"""
Ferramenta: Backup e Exportação de Drivers do Windows.
Listagem de drivers de terceiros, filtros por classe/dispositivo e exportação via pnputil.
"""
from pathlib import Path
import subprocess
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.system.driver_backup.logic import (
    export_drivers_to_folder, list_third_party_drivers
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class DriverBackupTool(Tool):
    id = "system.driver_backup"
    name = "Backup de Drivers do Windows"
    category = "Sistema"
    description = "Exportação e backup de drivers de terceiros instalados com filtro por classe de dispositivo"
    keywords = ["driver", "drivers", "backup", "pnputil", "inf", "hardware", "dispositivos", "exportar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DriverBackupView(self, parent)


COLUMNS = [
    Column("published_name", "INF Publicado", width=130),
    Column("original_name", "Arquivo Original", width=170, tooltip=True),
    Column("provider", "Provedor / Fabricante", stretch=True, tooltip=True),
    Column("class_name", "Classe do Dispositivo", width=210, tooltip=True),
    Column("version", "Versão", width=140),
    Column("date", "Data do Driver", width=120),
]


class DriverBackupView(QWidget):
    def __init__(self, tool: DriverBackupTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._drivers = []
        self._build_ui()
        self._refresh_drivers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_tool_header(self.tool))

        # Barra de Filtros Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.chk_select_all = QCheckBox("Marcar Visíveis")
        self.chk_select_all.toggled.connect(self._on_select_all_toggled)
        top_bar.addWidget(self.chk_select_all)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Fabricante, INF, classe ou versão...")
        self.txt_filter.textChanged.connect(self._apply_filters)
        top_bar.addWidget(self.txt_filter, stretch=1)

        top_bar.addWidget(QLabel("Classe:"))
        self.cmb_class = QComboBox()
        self.cmb_class.addItem("Todas as Classes", "")
        self.cmb_class.currentIndexChanged.connect(self._apply_filters)
        top_bar.addWidget(self.cmb_class)

        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._refresh_drivers)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("0 drivers")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela com Checkboxes
        self.table = DataTableView(COLUMNS, key="published_name", parent=self, checkable=True)
        self.table.sortByColumn(3, Qt.AscendingOrder)
        self.table.checkedChanged.connect(self._on_checked_changed)
        layout.addWidget(self.table, stretch=1)

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
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

    def _refresh_drivers(self):
        self._drivers = list_third_party_drivers()

        # Atualiza combo de classes de dispositivo
        classes = sorted({d.get("class_name", "") for d in self._drivers if d.get("class_name")})
        current_cls = self.cmb_class.currentData() or ""
        self.cmb_class.blockSignals(True)
        self.cmb_class.clear()
        self.cmb_class.addItem("Todas as Classes", "")
        for c in classes:
            self.cmb_class.addItem(c, c)
        idx = self.cmb_class.findData(current_cls)
        if idx >= 0:
            self.cmb_class.setCurrentIndex(idx)
        self.cmb_class.blockSignals(False)

        self.table.set_records(self._drivers)
        self._apply_filters()

    def _apply_filters(self):
        wanted_cls = self.cmb_class.currentData() or ""
        self.table.proxy.set_predicate(
            None if not wanted_cls else (lambda rec: rec.get("class_name") == wanted_cls)
        )
        self.table.proxy.set_text_filter(self.txt_filter.text())
        self._update_count()

    def _on_select_all_toggled(self, checked: bool):
        self.table.set_all_visible_checked(checked)

    def _on_checked_changed(self, count: int):
        if count > 0:
            self.btn_export.setText(f"Exportar Drivers Marcados ({count})")
        else:
            self.btn_export.setText("Exportar Todos os Drivers")
        self._update_count()

    def _update_count(self):
        total = len(self._drivers)
        shown = self.table.visible_count()
        checked = len(self.table.checked_records())
        txt = f"{total} drivers" if shown == total else f"{shown} de {total} drivers"
        if checked > 0:
            txt += f" ({checked} marcado(s))"
        self.lbl_count.setText(txt)

    def _on_browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Backup de Drivers")
        if d:
            self.txt_dest.setText(d)

    def _on_export(self):
        dest_str = self.txt_dest.text().strip()
        if not dest_str:
            QMessageBox.warning(self, "Aviso", "Informe a pasta de destino para o backup.")
            return

        if not is_admin():
            if prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason="A exportação de pacotes de drivers do repositório do Windows via pnputil requer privilégios de Administrador.",
            ):
                return

        checked_records = self.table.checked_records()
        selected_infs: Optional[List[str]] = (
            [str(r["published_name"]) for r in checked_records if r.get("published_name")]
            if checked_records
            else None
        )

        dest_path = Path(dest_str)
        self.btn_export.setEnabled(False)
        self.lbl_status.setText("Exportando drivers do sistema (isso pode levar alguns minutos)...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Invocando pnputil para exportação de drivers...")
            ok, msg, count = export_drivers_to_folder(dest_path, published_names=selected_infs)
            ctx.progress(100, 100, "Concluído!")
            return ok, msg, count

        def _done(result, exc):
            self.btn_export.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha na exportação: {exc}")
                return

            ok, msg, _count = result
            if ok:
                self.lbl_status.setText("Backup concluído com sucesso!")
                ans = QMessageBox.question(
                    self,
                    "Backup Concluído",
                    f"{msg}\n\nDeseja abrir a pasta onde os drivers foram salvos?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if ans == QMessageBox.Yes and dest_path.exists():
                    subprocess.Popen(f'explorer "{dest_path}"')
            else:
                self.lbl_status.setText("Erro na exportação.")
                if not is_admin():
                    prompt_elevation_dialog(self, tool_name=self.tool.name, reason=msg)
                else:
                    QMessageBox.critical(self, "Erro", msg)

        def _on_prog(cur, tot, msg):
            if msg:
                self.lbl_status.setText(msg)

        run_task(_work, on_done=_done, on_progress=_on_prog)
