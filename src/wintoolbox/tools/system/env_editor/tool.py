"""
Ferramenta: Editor de Variáveis de Ambiente e PATH.
Visualização de variáveis de usuário/sistema e editor visual da variável PATH com validação de pastas órfãs.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.env_editor.logic import (
    delete_environment_variable, get_environment_variables, get_path_entries,
    save_path_entries, set_environment_variable
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)


@register
class EnvEditorTool(Tool):
    id = "system.env_editor"
    name = "Variáveis de Ambiente e PATH"
    category = "Sistema"
    description = "Gerenciamento de variáveis de ambiente do Usuário e Sistema com editor visual e validação do PATH"
    keywords = ["ambiente", "path", "variáveis", "env", "sistema", "usuário", "pastas", "cmd"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return EnvEditorView(self, parent)


class EnvEditorView(QWidget):
    def __init__(self, tool: EnvEditorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()
        self._reload_data()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # Seletor de Escopo no Topo
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Escopo:"))
        self.cmb_scope = QComboBox()
        self.cmb_scope.addItem("Variáveis do Usuário Atual (HKCU)", "user")
        self.cmb_scope.addItem("Variáveis do Sistema / Máquina (HKLM - Requer Admin)", "system")
        self.cmb_scope.currentIndexChanged.connect(self._reload_data)
        top_bar.addWidget(self.cmb_scope)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._reload_data)
        top_bar.addWidget(self.btn_refresh)

        top_bar.addStretch()
        root_layout.addLayout(top_bar)

        # Abas
        self.tabs = QTabWidget()
        self.tab_vars = self._build_vars_tab()
        self.tab_path = self._build_path_tab()
        self.tabs.addTab(self.tab_vars, "Todas as Variáveis")
        self.tabs.addTab(self.tab_path, "Editor Visual do PATH")
        root_layout.addWidget(self.tabs)

    # -------------------------------------------------------------------------
    # Aba 1: Todas as Variáveis
    # -------------------------------------------------------------------------
    def _build_vars_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.table_vars = QTableWidget()
        self.table_vars.setColumnCount(2)
        self.table_vars.setHorizontalHeaderLabels(["Nome da Variável", "Valor"])
        self.table_vars.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_vars.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_vars.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_vars.setSelectionMode(QTableWidget.SingleSelection)
        self.table_vars.setAlternatingRowColors(True)
        enable_sorting_on_table(self.table_vars)
        layout.addWidget(self.table_vars)

        btn_bar = QHBoxLayout()
        btn_add = QPushButton("Nova Variável...")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add_var)
        btn_bar.addWidget(btn_add)

        btn_edit = QPushButton("Editar...")
        btn_edit.clicked.connect(self._on_edit_var)
        btn_bar.addWidget(btn_edit)

        btn_delete = QPushButton("Excluir")
        btn_delete.clicked.connect(self._on_delete_var)
        btn_bar.addWidget(btn_delete)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)
        return widget

    # -------------------------------------------------------------------------
    # Aba 2: Editor Especial do PATH
    # -------------------------------------------------------------------------
    def _build_path_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        lbl_info = QLabel("Caminhos incluídos na variável PATH (a ordem de prioridade segue do topo para a base):")
        lbl_info.setStyleSheet("color: #888890;")
        layout.addWidget(lbl_info)

        body = QHBoxLayout()
        self.list_path = QListWidget()
        body.addWidget(self.list_path)

        # Botões laterais
        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        self.btn_up = QPushButton("Mover para Cima")
        self.btn_up.clicked.connect(self._on_path_up)
        btn_col.addWidget(self.btn_up)

        self.btn_down = QPushButton("Mover para Baixo")
        self.btn_down.clicked.connect(self._on_path_down)
        btn_col.addWidget(self.btn_down)

        btn_col.addSpacing(12)

        self.btn_add_folder = QPushButton("Adicionar Pasta...")
        self.btn_add_folder.clicked.connect(self._on_add_path_folder)
        btn_col.addWidget(self.btn_add_folder)

        self.btn_remove_path = QPushButton("Remover Pasta")
        self.btn_remove_path.clicked.connect(self._on_remove_path_entry)
        btn_col.addWidget(self.btn_remove_path)

        self.btn_clean_invalid = QPushButton("Limpar Pastas Órfãs")
        self.btn_clean_invalid.clicked.connect(self._on_clean_invalid_paths)
        btn_col.addWidget(self.btn_clean_invalid)

        btn_col.addStretch()
        body.addLayout(btn_col)
        layout.addLayout(body)

        btn_save_path = QPushButton("Salvar Alterações no PATH")
        btn_save_path.setProperty("class", "primary")
        btn_save_path.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        btn_save_path.clicked.connect(self._on_save_path)
        layout.addWidget(btn_save_path)

        return widget

    def _reload_data(self):
        scope = self.cmb_scope.currentData()

        # 1. Carrega Variáveis
        vars_dict = get_environment_variables(scope)
        with batch_table_update(self.table_vars):
            self.table_vars.setRowCount(len(vars_dict))
            for row, (k, v) in enumerate(sorted(vars_dict.items())):
                self.table_vars.setItem(row, 0, SmartTableWidgetItem(k, user_data=k))
                self.table_vars.setItem(row, 1, SmartTableWidgetItem(v))

        # 2. Carrega PATH
        self.list_path.clear()
        path_entries = get_path_entries(scope)
        for ent in path_entries:
            raw = ent["raw_path"]
            exists = ent["exists"]
            item = QListWidgetItem()
            if exists:
                item.setText(raw)
            else:
                item.setText(f"[Inexistente / Órfão] {raw}")
                item.setForeground(Qt.red)
            item.setData(Qt.UserRole, raw)
            item.setData(Qt.UserRole + 1, exists)
            self.list_path.addItem(item)

    def _on_add_var(self):
        self._show_var_dialog(title="Nova Variável de Ambiente")

    def _on_edit_var(self):
        selected = self.table_vars.selectedItems()
        if not selected:
            QMessageBox.information(self, "Aviso", "Selecione uma variável para editar.")
            return
        row = selected[0].row()
        name = self.table_vars.item(row, 0).text()
        val = self.table_vars.item(row, 1).text()
        self._show_var_dialog(title="Editar Variável de Ambiente", name=name, value=val, edit_mode=True)

    def _show_var_dialog(self, title: str, name: str = "", value: str = "", edit_mode: bool = False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedWidth(460)
        dlg_layout = QVBoxLayout(dialog)

        form = QFormLayout()
        txt_name = QLineEdit(name)
        if edit_mode:
            txt_name.setEnabled(False)
        txt_val = QLineEdit(value)

        form.addRow("Nome da Variável:", txt_name)
        form.addRow("Valor:", txt_val)
        dlg_layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_ok = QPushButton("Salvar")
        btn_ok.setProperty("class", "primary")
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)

        def _save():
            v_name = txt_name.text().strip()
            v_val = txt_val.text().strip()
            if not v_name:
                QMessageBox.warning(dialog, "Aviso", "O nome não pode ser vazio.")
                return
            scope = self.cmb_scope.currentData()
            ok, msg = set_environment_variable(v_name, v_val, scope=scope)
            if ok:
                QMessageBox.information(dialog, "Sucesso", msg)
                dialog.accept()
                self._reload_data()
            else:
                if not is_admin() and scope == "system":
                    ans = QMessageBox.question(dialog, "Admin", f"{msg}\nDeseja reiniciar como Administrador?", QMessageBox.Yes | QMessageBox.No)
                    if ans == QMessageBox.Yes:
                        request_elevation()
                else:
                    QMessageBox.critical(dialog, "Erro", msg)

        btn_ok.clicked.connect(_save)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()

    def _on_delete_var(self):
        selected = self.table_vars.selectedItems()
        if not selected:
            QMessageBox.information(self, "Aviso", "Selecione uma variável para excluir.")
            return
        row = selected[0].row()
        name = self.table_vars.item(row, 0).text()

        confirm = QMessageBox.question(self, "Confirmar Exclusão", f"Deseja realmente excluir a variável '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        scope = self.cmb_scope.currentData()
        ok, msg = delete_environment_variable(name, scope=scope)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._reload_data()
        else:
            QMessageBox.critical(self, "Erro", msg)

    # Métodos do PATH
    def _on_path_up(self):
        row = self.list_path.currentRow()
        if row > 0:
            item = self.list_path.takeItem(row)
            self.list_path.insertItem(row - 1, item)
            self.list_path.setCurrentRow(row - 1)

    def _on_path_down(self):
        row = self.list_path.currentRow()
        if row < self.list_path.count() - 1:
            item = self.list_path.takeItem(row)
            self.list_path.insertItem(row + 1, item)
            self.list_path.setCurrentRow(row + 1)

    def _on_add_path_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório para o PATH")
        if folder:
            item = QListWidgetItem(folder)
            item.setData(Qt.UserRole, folder)
            item.setData(Qt.UserRole + 1, True)
            self.list_path.addItem(item)

    def _on_remove_path_entry(self):
        row = self.list_path.currentRow()
        if row >= 0:
            self.list_path.takeItem(row)

    def _on_clean_invalid_paths(self):
        removed = 0
        for i in reversed(range(self.list_path.count())):
            item = self.list_path.item(i)
            exists = item.data(Qt.UserRole + 1)
            if not exists:
                self.list_path.takeItem(i)
                removed += 1
        QMessageBox.information(self, "Limpeza do PATH", f"{removed} caminho(s) órfão(s) / inexistente(s) foram removidos da lista.")

    def _on_save_path(self):
        entries = []
        for i in range(self.list_path.count()):
            item = self.list_path.item(i)
            raw = item.data(Qt.UserRole)
            if raw:
                entries.append(raw)

        scope = self.cmb_scope.currentData()
        ok, msg = save_path_entries(entries, scope=scope)
        if ok:
            QMessageBox.information(self, "Sucesso", f"{msg}\nO sistema foi notificado via broadcast.")
            self._reload_data()
        else:
            if not is_admin() and scope == "system":
                ans = QMessageBox.question(self, "Admin", f"{msg}\nDeseja reiniciar como Administrador?", QMessageBox.Yes | QMessageBox.No)
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)
