"""
Ferramenta: Gerenciador de Inicialização do Windows.
Listagem com status Ativo/Desativado, ícones, seleção múltipla por checkbox, ativação/desativação em lote e remoção.
"""
import os
import subprocess
from typing import List, Optional
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.startup_manager.logic import (
    add_registry_startup_item,
    list_startup_items,
    remove_startup_item,
    set_multiple_startup_items_enabled,
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class StartupManagerTool(Tool):
    id = "system.startup_manager"
    name = "Gerenciador de Inicialização"
    category = "Sistema"
    description = "Gerenciamento de programas que iniciam com o Windows: ativar, desativar ou remover em lote"
    keywords = ["startup", "inicialização", "boot", "run", "programas", "msconfig", "auto", "iniciar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return StartupManagerView(self, parent)


COLUMNS = [
    Column("name", "Programa", width=220, tooltip=True, icon_key="exe_path", fallback_icon=True),
    Column("status_label", "Status", width=110),
    Column("command", "Comando / Caminho", stretch=True, tooltip=True),
    Column("location", "Origem / Localização", width=210),
]


class StartupManagerView(QWidget):
    def __init__(self, tool: StartupManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._raw_items = []
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_tool_header(self.tool))

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.chk_select_all = QCheckBox("Marcar Visíveis")
        self.chk_select_all.toggled.connect(self._on_select_all_toggled)
        top_bar.addWidget(self.chk_select_all)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Nome do programa, caminho ou origem...")
        self.txt_filter.textChanged.connect(self._apply_filters)
        top_bar.addWidget(self.txt_filter, stretch=1)

        top_bar.addWidget(QLabel("Estado:"))
        self.cmb_state = QComboBox()
        self.cmb_state.addItems(["Todos", "Apenas Ativos", "Apenas Desativados"])
        self.cmb_state.currentIndexChanged.connect(self._apply_filters)
        top_bar.addWidget(self.cmb_state)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._refresh_list)
        top_bar.addWidget(self.btn_refresh)

        self.btn_add = QPushButton("Adicionar Programa...")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.clicked.connect(self._on_add_item)
        top_bar.addWidget(self.btn_add)

        self.lbl_count = QLabel("0 itens")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)
        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="uid", parent=self, checkable=True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.checkedChanged.connect(self._on_checked_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        t = get_current_tokens()
        self.table.source_model.foreground = lambda rec, key: (
            (t.status_success if rec.get("is_enabled") else t.status_warning) if key == "status_label" else (
                t.text_muted if not rec.get("is_enabled") else None
            )
        )
        layout.addWidget(self.table, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_enable = QPushButton("Ativar")
        self.btn_enable.clicked.connect(lambda: self._on_set_enabled(True))
        bottom_bar.addWidget(self.btn_enable)

        self.btn_disable = QPushButton("Desativar")
        self.btn_disable.clicked.connect(lambda: self._on_set_enabled(False))
        bottom_bar.addWidget(self.btn_disable)

        self.btn_open_file = QPushButton("Abrir Local do Arquivo")
        self.btn_open_file.clicked.connect(self._on_open_file_location)
        bottom_bar.addWidget(self.btn_open_file)

        bottom_bar.addStretch()

        self.btn_remove = QPushButton("Remover da Inicialização")
        self.btn_remove.setProperty("class", "danger")
        self.btn_remove.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_remove.clicked.connect(self._on_remove_item)
        bottom_bar.addWidget(self.btn_remove)

        layout.addLayout(bottom_bar)

    def _refresh_list(self):
        self._raw_items = list_startup_items()
        self.table.set_records(self._raw_items)
        self._apply_filters()

    def _apply_filters(self):
        idx = self.cmb_state.currentIndex()
        if idx == 1:
            self.table.proxy.set_predicate(lambda r: bool(r.get("is_enabled", True)))
        elif idx == 2:
            self.table.proxy.set_predicate(lambda r: not bool(r.get("is_enabled", True)))
        else:
            self.table.proxy.set_predicate(None)
        self.table.proxy.set_text_filter(self.txt_filter.text())
        self._update_count()

    def _on_select_all_toggled(self, checked: bool):
        self.table.set_all_visible_checked(checked)

    def _on_checked_changed(self, count: int):
        suffix = f" Marcados ({count})" if count > 0 else ""
        self.btn_enable.setText(f"Ativar{suffix}")
        self.btn_disable.setText(f"Desativar{suffix}")
        self.btn_remove.setText(f"Remover{suffix}" if count > 0 else "Remover da Inicialização")
        self._update_count()

    def _update_count(self):
        total = len(self._raw_items)
        active = sum(1 for r in self._raw_items if r.get("is_enabled"))
        inactive = total - active
        checked = len(self.table.checked_records())
        txt = f"{total} programas ({active} ativos, {inactive} desativados)"
        if checked > 0:
            txt += f" | {checked} marcado(s)"
        self.lbl_count.setText(txt)

    def _on_context_menu(self, pos: QPoint):
        rec = self.table.record_at_pos(pos)
        if not rec:
            return

        is_checked = self.table.is_record_checked(rec)
        checked_records = self.table.checked_records()
        targets = checked_records if checked_records else [rec]
        label_suffix = f" ({len(targets)} itens)" if len(targets) > 1 else f" '{rec['name']}'"

        menu = QMenu(self)
        act_toggle = menu.addAction("Desmarcar Item" if is_checked else "Marcar Item")
        menu.addSeparator()
        act_enable = menu.addAction(f"Ativar na Inicialização{label_suffix}")
        act_disable = menu.addAction(f"Desativar na Inicialização{label_suffix}")
        menu.addSeparator()
        act_open = menu.addAction("Abrir Local do Executável")
        act_remove = menu.addAction(f"Remover Definitivamente{label_suffix}")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_toggle:
            self.table.toggle_record_checked(rec)
        elif chosen == act_enable:
            self._apply_enabled_to_targets(targets, True)
        elif chosen == act_disable:
            self._apply_enabled_to_targets(targets, False)
        elif chosen == act_open:
            self._open_file_for_item(rec)
        elif chosen == act_remove:
            self._remove_targets(targets)

    def _on_set_enabled(self, enabled: bool):
        targets = self.table.target_records()
        if not targets:
            QMessageBox.information(self, "Aviso", "Selecione ou marque pelo menos um programa na lista.")
            return
        self._apply_enabled_to_targets(targets, enabled)

    def _apply_enabled_to_targets(self, targets: List[dict], enabled: bool):
        needs_hklm = any(t.get("root") == "HKLM" for t in targets)
        if needs_hklm and not is_admin():
            if prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason="Alterar programas de inicialização de 'Todos os Usuários' (HKLM) requer privilégios de Administrador.",
            ):
                return

        ok, msg = set_multiple_startup_items_enabled(targets, enabled)
        if ok:
            self.table.clear_checked()
            self.chk_select_all.blockSignals(True)
            self.chk_select_all.setChecked(False)
            self.chk_select_all.blockSignals(False)
            self._refresh_list()
            QMessageBox.information(self, "Sucesso", msg)
        elif not is_admin():
            prompt_elevation_dialog(self, tool_name=self.tool.name, reason=msg)
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _on_remove_item(self):
        targets = self.table.target_records()
        if not targets:
            QMessageBox.information(self, "Aviso", "Selecione ou marque pelo menos um item na lista para remover.")
            return
        self._remove_targets(targets)

    def _remove_targets(self, targets: List[dict]):
        desc = f"'{targets[0]['name']}'" if len(targets) == 1 else f"{len(targets)} programas selecionados"
        confirm = QMessageBox.question(
            self,
            "Confirmar Remoção",
            f"Deseja realmente remover {desc} da inicialização automática?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        errors = []
        for item in targets:
            ok, msg = remove_startup_item(item)
            if not ok:
                errors.append(msg)

        self.table.clear_checked()
        self._refresh_list()
        if not errors:
            QMessageBox.information(self, "Sucesso", "Item(ns) removido(s) com sucesso.")
        elif not is_admin():
            prompt_elevation_dialog(self, tool_name=self.tool.name, reason="\n".join(errors[:3]))
        else:
            QMessageBox.critical(self, "Erro", "\n".join(errors[:4]))

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
            f, _ = QFileDialog.getOpenFileName(
                dialog, "Selecionar Executável", "", "Executáveis (*.exe *.bat *.cmd);;Todos os Arquivos (*.*)"
            )
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
            elif not is_admin() and chk_all.isChecked():
                prompt_elevation_dialog(dialog, tool_name=self.tool.name, reason=msg)
            else:
                QMessageBox.critical(dialog, "Erro", msg)

        btn_ok.clicked.connect(_save)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()

    def _on_open_file_location(self):
        item = self.table.current_record()
        if not item:
            QMessageBox.information(self, "Aviso", "Selecione um item na lista.")
            return
        self._open_file_for_item(item)

    def _open_file_for_item(self, item: dict):
        exe = item.get("exe_path") or ""
        if exe and os.path.exists(exe):
            subprocess.Popen(f'explorer /select,"{exe}"')
        else:
            QMessageBox.warning(self, "Aviso", f"Não foi possível localizar o arquivo físico:\n{exe or item.get('command', '')}")
