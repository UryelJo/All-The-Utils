"""
Ferramenta: Gerenciador de Inicialização do Windows.
Listagem, adição e remoção de programas iniciados com o Windows.
"""
import os
import subprocess
from typing import Optional
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.startup_manager.logic import (
    add_registry_startup_item, list_startup_items, remove_startup_item
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)


@register
class StartupManagerTool(Tool):
    id = "system.startup_manager"
    name = "Gerenciador de Inicialização"
    category = "Sistema"
    description = "Gerenciamento de programas que iniciam automaticamente com o Windows (Registro e Startup)"
    keywords = ["startup", "inicialização", "boot", "run", "programas", "msconfig", "auto", "iniciar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return StartupManagerView(self, parent)


class StartupManagerView(QWidget):
    def __init__(self, tool: StartupManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._raw_items = []
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._refresh_list)
        top_bar.addWidget(self.btn_refresh)

        self.btn_add = QPushButton("Adicionar Programa...")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.clicked.connect(self._on_add_item)
        top_bar.addWidget(self.btn_add)

        top_bar.addStretch()

        self.lbl_count = QLabel("0 itens")
        self.lbl_count.setStyleSheet("color: #888890; font-weight: 500;")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nome", "Comando / Caminho", "Origem / Localização"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table)

        # Barra Inferior
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_open_file = QPushButton("Abrir Local do Arquivo")
        self.btn_open_file.clicked.connect(self._on_open_file_location)
        bottom_bar.addWidget(self.btn_open_file)

        bottom_bar.addStretch()

        self.btn_remove = QPushButton("Remover da Inicialização")
        self.btn_remove.setProperty("class", "danger")
        self.btn_remove.setStyleSheet("background-color: #dc3545; color: white;")
        self.btn_remove.clicked.connect(self._on_remove_item)
        bottom_bar.addWidget(self.btn_remove)

        layout.addLayout(bottom_bar)

    def _get_selected_item(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row >= 0:
            it = self.table.item(row, 0)
            if it:
                d = it.data(Qt.UserRole)
                if isinstance(d, dict):
                    return d
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            it = self.table.item(row, 0)
            if it:
                d = it.data(Qt.UserRole)
                if isinstance(d, dict):
                    return d
            if 0 <= row < len(self._raw_items):
                return self._raw_items[row]
        return None

    def _refresh_list(self):
        self._raw_items = list_startup_items()
        with batch_table_update(self.table):
            self.table.setRowCount(len(self._raw_items))
            for row, item in enumerate(self._raw_items):
                self.table.setItem(row, 0, SmartTableWidgetItem(item["name"], user_data=item))
                self.table.setItem(row, 1, SmartTableWidgetItem(item["command"]))
                self.table.setItem(row, 2, SmartTableWidgetItem(item["location"]))

        self.lbl_count.setText(f"{len(self._raw_items)} programas na inicialização")

    def _on_remove_item(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Aviso", "Selecione um item na lista para remover.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar Remoção",
            f"Deseja realmente remover '{item['name']}' da inicialização automática?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        ok, msg = remove_startup_item(item)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_list()
        else:
            if not is_admin():
                ans = QMessageBox.question(
                    self,
                    "Privilégios Necessários",
                    f"{msg}\n\nDeseja reiniciar o aplicativo como Administrador?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)

    def _on_add_item(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Adicionar Programa à Inicialização")
        dialog.setFixedWidth(450)
        dlg_layout = QVBoxLayout(dialog)

        form = QFormLayout()
        txt_name = QLineEdit()
        txt_path = QLineEdit()

        btn_browse = QPushButton("Procurar...")
        def _browse():
            f, _ = QFileDialog.getOpenFileName(dialog, "Selecionar Executável", "", "Executáveis (*.exe *.bat *.cmd);;Todos os Arquivos (*.*)")
            if f:
                txt_path.setText(f)
                if not txt_name.text():
                    txt_name.setText(os.path.splitext(os.path.basename(f))[0])

        btn_browse.clicked.connect(_browse)

        path_box = QHBoxLayout()
        path_box.addWidget(txt_path)
        path_box.addWidget(btn_browse)

        chk_all = QCheckBox("Adicionar para todos os usuários do computador (requer Admin)")

        form.addRow("Nome de Exibição:", txt_name)
        form.addRow("Executável / Comando:", path_box)
        form.addRow("", chk_all)
        dlg_layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_ok = QPushButton("Adicionar")
        btn_ok.setProperty("class", "primary")
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)

        def _save():
            if not txt_name.text().strip() or not txt_path.text().strip():
                QMessageBox.warning(dialog, "Aviso", "Preencha o nome e o caminho do programa.")
                return
            ok, msg = add_registry_startup_item(txt_name.text(), txt_path.text(), all_users=chk_all.isChecked())
            if ok:
                QMessageBox.information(dialog, "Sucesso", msg)
                dialog.accept()
                self._refresh_list()
            else:
                QMessageBox.critical(dialog, "Erro", msg)

        btn_ok.clicked.connect(_save)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()

    def _on_open_file_location(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Aviso", "Selecione um item na lista.")
            return

        cmd = item["command"].strip('"').split('"')[0]

        # Extrai caminho se for executável com argumentos
        parts = cmd.split()
        exe = parts[0] if parts else cmd
        exe = exe.strip('"')

        if os.path.exists(exe):
            subprocess.Popen(f'explorer /select,"{exe}"')
        else:
            QMessageBox.warning(self, "Aviso", f"Não foi possível localizar o arquivo físico:\n{exe}")
