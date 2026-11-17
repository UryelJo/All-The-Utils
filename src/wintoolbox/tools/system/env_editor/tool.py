"""
Ferramenta: Editor de Variáveis de Ambiente e PATH.
Visualização de variáveis de usuário/sistema, edição em formato de tabela (separador ';') e editor visual do PATH.
"""
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.env_editor.logic import (
    delete_environment_variable, get_environment_variables, get_path_entries,
    save_path_entries, set_environment_variable
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, batch_table_update, enable_sorting_on_table
)
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class EnvEditorTool(Tool):
    id = "system.env_editor"
    name = "Variáveis de Ambiente e PATH"
    category = "Sistema"
    description = "Gerenciamento de variáveis de ambiente do Usuário e Sistema com edição em tabela e validação do PATH"
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
        root_layout.setContentsMargins(20, 20, 20, 16)
        root_layout.setSpacing(10)
        root_layout.addWidget(make_tool_header(self.tool))

        # Seletor de Escopo no Topo
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Escopo:"))
        self.cmb_scope = QComboBox()
        self.cmb_scope.addItem("Variáveis do Usuário Atual (HKCU)", "user")
        self.cmb_scope.addItem("Variáveis do Sistema / Máquina (HKLM - Requer Admin)", "system")
        self.cmb_scope.currentIndexChanged.connect(self._on_scope_changed)
        top_bar.addWidget(self.cmb_scope)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Filtrar por nome ou valor...")
        self.txt_filter.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._reload_data)
        top_bar.addWidget(self.btn_refresh)

        root_layout.addLayout(top_bar)

        # Abas
        self.tabs = QTabWidget()
        self.tab_vars = self._build_vars_tab()
        self.tab_path = self._build_path_tab()
        self.tabs.addTab(self.tab_vars, "Todas as Variáveis")
        self.tabs.addTab(self.tab_path, "Editor Visual do PATH")
        root_layout.addWidget(self.tabs, stretch=1)

    def _on_scope_changed(self):
        scope = self.cmb_scope.currentData()
        if scope == "system" and not is_admin():
            prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason="Para editar ou salvar Variáveis do Sistema (HKLM), são necessários privilégios de Administrador.",
            )
        self._reload_data()

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
        self.table_vars.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_vars.doubleClicked.connect(lambda _idx: self._on_edit_var())
        enable_sorting_on_table(self.table_vars)
        layout.addWidget(self.table_vars)

        btn_bar = QHBoxLayout()
        btn_add = QPushButton("Nova Variável...")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add_var)
        btn_bar.addWidget(btn_add)

        btn_edit = QPushButton("Editar em Tabela...")
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
        lbl_info.setProperty("class", "secondary")
        layout.addWidget(lbl_info)

        body = QHBoxLayout()
        self.list_path = QListWidget()
        body.addWidget(self.list_path)

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

        self._apply_filter()

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

    def _apply_filter(self):
        q = self.txt_filter.text().strip().lower() if hasattr(self, "txt_filter") else ""
        for r in range(self.table_vars.rowCount()):
            k_txt = (self.table_vars.item(r, 0).text() if self.table_vars.item(r, 0) else "").lower()
            v_txt = (self.table_vars.item(r, 1).text() if self.table_vars.item(r, 1) else "").lower()
            self.table_vars.setRowHidden(r, bool(q and q not in k_txt and q not in v_txt))

    def _on_add_var(self):
        self._show_var_dialog(title="Nova Variável de Ambiente")

    def _on_edit_var(self):
        row = self.table_vars.currentRow()
        if row < 0:
            selected = self.table_vars.selectedItems()
            if not selected:
                QMessageBox.information(self, "Aviso", "Selecione uma variável para editar.")
                return
            row = selected[0].row()
        name = self.table_vars.item(row, 0).text()
        val = self.table_vars.item(row, 1).text()
        self._show_var_dialog(title=f"Editar Variável '{name}'", name=name, value=val, edit_mode=True)

    def _show_var_dialog(self, title: str, name: str = "", value: str = "", edit_mode: bool = False):
        """
        Exibe diálogo de edição da variável em formato de tabela onde cada item separado por ';'
        é uma linha individual editável.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(620, 420)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(10)

        form = QFormLayout()
        txt_name = QLineEdit(name)
        if edit_mode:
            txt_name.setReadOnly(True)
        form.addRow("Nome da Variável:", txt_name)
        dlg_layout.addLayout(form)

        lbl_hint = QLabel(
            "Valores da variável (cada linha abaixo representa um item separado por ';' no Windows — "
            "dê duplo clique na célula para editar):"
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setProperty("class", "secondary")
        dlg_layout.addWidget(lbl_hint)

        body = QHBoxLayout()
        table_vals = QTableWidget(0, 1, dialog)
        table_vals.setHorizontalHeaderLabels(["Valor / Caminho"])
        table_vals.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table_vals.setSelectionBehavior(QTableWidget.SelectRows)
        table_vals.setSelectionMode(QTableWidget.SingleSelection)
        table_vals.setAlternatingRowColors(True)
        body.addWidget(table_vals, stretch=1)

        parts: List[str] = [p for p in value.split(";") if p != ""] if value else [""]
        table_vals.setRowCount(len(parts))
        for idx, part in enumerate(parts):
            it = QTableWidgetItem(part)
            it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            table_vals.setItem(idx, 0, it)

        side_btns = QVBoxLayout()
        side_btns.setSpacing(6)

        btn_add_row = QPushButton("Adicionar Linha")
        btn_add_folder = QPushButton("Adicionar Pasta...")
        btn_remove_row = QPushButton("Remover Linha")
        btn_move_up = QPushButton("Mover para Cima")
        btn_move_down = QPushButton("Mover para Baixo")

        def _add_row(initial_text: str = ""):
            r = table_vals.rowCount()
            table_vals.insertRow(r)
            it = QTableWidgetItem(initial_text)
            it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            table_vals.setItem(r, 0, it)
            table_vals.setCurrentCell(r, 0)
            if not initial_text:
                table_vals.editItem(it)

        def _browse_folder():
            folder = QFileDialog.getExistingDirectory(dialog, "Selecionar Diretório")
            if folder:
                # Se a primeira linha estiver vazia, preenche ela; senão adiciona nova
                if table_vals.rowCount() == 1 and not (table_vals.item(0, 0).text().strip() if table_vals.item(0, 0) else ""):
                    table_vals.item(0, 0).setText(folder)
                else:
                    _add_row(folder)

        def _remove_row():
            r = table_vals.currentRow()
            if r >= 0:
                table_vals.removeRow(r)

        def _move_up():
            r = table_vals.currentRow()
            if r > 0:
                t_cur = table_vals.item(r, 0).text() if table_vals.item(r, 0) else ""
                t_prev = table_vals.item(r - 1, 0).text() if table_vals.item(r - 1, 0) else ""
                table_vals.item(r - 1, 0).setText(t_cur)
                table_vals.item(r, 0).setText(t_prev)
                table_vals.setCurrentCell(r - 1, 0)

        def _move_down():
            r = table_vals.currentRow()
            if 0 <= r < table_vals.rowCount() - 1:
                t_cur = table_vals.item(r, 0).text() if table_vals.item(r, 0) else ""
                t_next = table_vals.item(r + 1, 0).text() if table_vals.item(r + 1, 0) else ""
                table_vals.item(r + 1, 0).setText(t_cur)
                table_vals.item(r, 0).setText(t_next)
                table_vals.setCurrentCell(r + 1, 0)

        btn_add_row.clicked.connect(lambda: _add_row(""))
        btn_add_folder.clicked.connect(_browse_folder)
        btn_remove_row.clicked.connect(_remove_row)
        btn_move_up.clicked.connect(_move_up)
        btn_move_down.clicked.connect(_move_down)

        side_btns.addWidget(btn_add_row)
        side_btns.addWidget(btn_add_folder)
        side_btns.addWidget(btn_remove_row)
        side_btns.addSpacing(8)
        side_btns.addWidget(btn_move_up)
        side_btns.addWidget(btn_move_down)
        side_btns.addStretch()
        body.addLayout(side_btns)
        dlg_layout.addLayout(body, stretch=1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_ok = QPushButton("Salvar Variável")
        btn_ok.setProperty("class", "primary")
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)

        def _save():
            v_name = txt_name.text().strip()
            if not v_name:
                QMessageBox.warning(dialog, "Aviso", "O nome da variável não pode ser vazio.")
                return
            collected_vals: List[str] = []
            for r in range(table_vals.rowCount()):
                cell = table_vals.item(r, 0)
                if cell:
                    txt = cell.text().strip()
                    if txt:
                        collected_vals.append(txt)
            v_val = ";".join(collected_vals)
            scope = self.cmb_scope.currentData()
            ok, msg = set_environment_variable(v_name, v_val, scope=scope)
            if ok:
                QMessageBox.information(dialog, "Sucesso", msg)
                dialog.accept()
                self._reload_data()
            else:
                if not is_admin() and scope == "system":
                    prompt_elevation_dialog(dialog, tool_name=self.tool.name, reason=msg)
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

        confirm = QMessageBox.question(
            self, "Confirmar Exclusão", f"Deseja realmente excluir a variável '{name}'?", QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        scope = self.cmb_scope.currentData()
        ok, msg = delete_environment_variable(name, scope=scope)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._reload_data()
        elif not is_admin() and scope == "system":
            prompt_elevation_dialog(self, tool_name=self.tool.name, reason=msg)
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
        QMessageBox.information(
            self, "Limpeza do PATH", f"{removed} caminho(s) órfão(s) / inexistente(s) foram removidos da lista."
        )

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
                prompt_elevation_dialog(self, tool_name=self.tool.name, reason=msg)
            else:
                QMessageBox.critical(self, "Erro", msg)
