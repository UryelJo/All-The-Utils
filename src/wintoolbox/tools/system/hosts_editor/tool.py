"""
Ferramenta: Editor Seguro do Arquivo Hosts do Windows.
Gerenciamento de redirecionamentos locais, bloqueios de domínio, backup e ordenação por colunas.
"""
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.hosts_editor.logic import (
    flush_dns_cache, list_hosts_backups, read_hosts_file, restore_hosts_backup, save_hosts_file
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, batch_table_update, enable_sorting_on_table
)
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class HostsEditorTool(Tool):
    id = "system.hosts_editor"
    name = "Editor do Arquivo Hosts"
    category = "Sistema"
    description = "Editor seguro do arquivo hosts do Windows com backup automático e alternância rápida de entradas"
    keywords = ["hosts", "dns", "ip", "redirecionar", "bloqueio", "dominio", "localhost", "rede"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HostsEditorView(self, parent)


class HostsEditorView(QWidget):
    def __init__(self, tool: HostsEditorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._entries = []
        self._build_ui()
        self._reload_hosts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_tool_header(self.tool))

        # Barra Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_refresh = QPushButton("Recarregar")
        self.btn_refresh.clicked.connect(self._reload_hosts)
        top_bar.addWidget(self.btn_refresh)

        self.btn_add = QPushButton("Adicionar Entrada...")
        self.btn_add.setProperty("class", "primary")
        self.btn_add.clicked.connect(self._on_add_entry)
        top_bar.addWidget(self.btn_add)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Filtrar por IP, domínio ou comentário...")
        self.txt_filter.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.lbl_count = QLabel("0 entradas")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela com Ordenação em Todas as Colunas
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Ativo", "Endereço IP", "Domínio / Hostname", "Comentário"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 160)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 220)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table, stretch=1)

        # Barra Inferior
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_remove = QPushButton("Remover Selecionado")
        self.btn_remove.clicked.connect(self._on_remove_selected)
        bottom_bar.addWidget(self.btn_remove)

        self.btn_restore_backup = QPushButton("Restaurar Backup...")
        self.btn_restore_backup.clicked.connect(self._on_restore_backup)
        bottom_bar.addWidget(self.btn_restore_backup)

        bottom_bar.addStretch()

        self.btn_save = QPushButton("Salvar Arquivo Hosts")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_save.clicked.connect(self._on_save_hosts)
        bottom_bar.addWidget(self.btn_save)

        layout.addLayout(bottom_bar)

    def _reload_hosts(self):
        self._entries = read_hosts_file()
        self._populate_table(self._entries)

    def _populate_table(self, entries: List[dict]):
        with batch_table_update(self.table):
            self.table.setRowCount(len(entries))
            for row, ent in enumerate(entries):
                is_on = bool(ent.get("is_enabled", True))
                chk_item = SmartTableWidgetItem("", sort_value=1 if is_on else 0)
                chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                chk_item.setCheckState(Qt.Checked if is_on else Qt.Unchecked)
                self.table.setItem(row, 0, chk_item)

                ip_str = ent.get("ip", "")
                self.table.setItem(row, 1, SmartTableWidgetItem(ip_str, sort_value=ip_str.lower()))

                host_str = ent.get("hostname", "")
                self.table.setItem(row, 2, SmartTableWidgetItem(host_str, sort_value=host_str.lower()))

                comm_str = ent.get("comment", "")
                self.table.setItem(row, 3, SmartTableWidgetItem(comm_str, sort_value=comm_str.lower()))

        self._apply_filter()

    def _apply_filter(self):
        q = self.txt_filter.text().strip().lower() if hasattr(self, "txt_filter") else ""
        shown = 0
        total = self.table.rowCount()
        for r in range(total):
            ip_txt = (self.table.item(r, 1).text() if self.table.item(r, 1) else "").lower()
            host_txt = (self.table.item(r, 2).text() if self.table.item(r, 2) else "").lower()
            comm_txt = (self.table.item(r, 3).text() if self.table.item(r, 3) else "").lower()
            visible = not q or (q in ip_txt or q in host_txt or q in comm_txt)
            self.table.setRowHidden(r, not visible)
            if visible:
                shown += 1
        self.lbl_count.setText(f"{total} entradas" if shown == total else f"{shown} de {total} entradas")

    def _collect_entries_from_table(self) -> List[dict]:
        collected = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            ip = self.table.item(row, 1)
            host = self.table.item(row, 2)
            comm = self.table.item(row, 3)
            collected.append({
                "is_enabled": (chk.checkState() == Qt.Checked) if chk else True,
                "ip": ip.text().strip() if ip else "",
                "hostname": host.text().strip() if host else "",
                "comment": comm.text().strip() if comm else "",
            })
        return collected

    def _on_add_entry(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Adicionar Entrada no Hosts")
        dialog.setFixedWidth(400)
        dlg_layout = QVBoxLayout(dialog)

        form = QFormLayout()
        txt_ip = QLineEdit("127.0.0.1")
        txt_host = QLineEdit()
        txt_host.setPlaceholderText("ex: meudominio.local ou site.com")
        txt_comm = QLineEdit()
        txt_comm.setPlaceholderText("Opcional")

        form.addRow("Endereço IP:", txt_ip)
        form.addRow("Hostname / Domínio:", txt_host)
        form.addRow("Comentário:", txt_comm)
        dlg_layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_ok = QPushButton("Adicionar")
        btn_ok.setProperty("class", "primary")
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)

        def _confirm():
            ip_val = txt_ip.text().strip()
            host_val = txt_host.text().strip()
            if not ip_val or not host_val:
                QMessageBox.warning(dialog, "Aviso", "Preencha o IP e o Hostname.")
                return
            current = self._collect_entries_from_table()
            current.append({
                "ip": ip_val,
                "hostname": host_val,
                "comment": txt_comm.text().strip(),
                "is_enabled": True,
            })
            self._entries = current
            dialog.accept()
            self._populate_table(self._entries)

        btn_ok.clicked.connect(_confirm)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()

    def _on_remove_selected(self):
        row = self.table.currentRow()
        if row < 0:
            selected = self.table.selectedItems()
            if not selected:
                QMessageBox.information(self, "Aviso", "Selecione uma linha para remover.")
                return
            row = selected[0].row()

        self.table.removeRow(row)
        self._entries = self._collect_entries_from_table()
        self._apply_filter()

    def _on_save_hosts(self):
        if not is_admin():
            if prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason="Salvar alterações no arquivo 'C:\\Windows\\System32\\drivers\\etc\\hosts' exige privilégios de Administrador.",
            ):
                return

        self._entries = self._collect_entries_from_table()
        ok, msg = save_hosts_file(self._entries, create_backup=True)
        if ok:
            flush_dns_cache()
            QMessageBox.information(self, "Sucesso", f"{msg}\nO cache DNS também foi limpo automaticamente.")
            self._reload_hosts()
        else:
            if not is_admin():
                prompt_elevation_dialog(self, tool_name=self.tool.name, reason=msg)
            else:
                QMessageBox.critical(self, "Erro", msg)

    def _on_restore_backup(self):
        backups = list_hosts_backups()
        if not backups:
            QMessageBox.information(self, "Backups", "Nenhum arquivo de backup anterior foi encontrado.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Restaurar Backup do Arquivo Hosts")
        dialog.setFixedWidth(500)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel("Selecione um ponto de backup para restaurar:"))
        list_bks = QListWidget()
        for b in backups:
            list_bks.addItem(b.name)
        list_bks.setCurrentRow(0)
        dlg_layout.addWidget(list_bks)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_ok = QPushButton("Restaurar Este Backup")
        btn_ok.setProperty("class", "primary")
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)

        def _do_restore():
            row = list_bks.currentRow()
            if row < 0 or row >= len(backups):
                return
            chosen = backups[row]
            ok, msg = restore_hosts_backup(chosen)
            if ok:
                flush_dns_cache()
                QMessageBox.information(dialog, "Sucesso", f"{msg}\nCache DNS renovado.")
                dialog.accept()
                self._reload_hosts()
            elif not is_admin():
                prompt_elevation_dialog(dialog, tool_name=self.tool.name, reason=msg)
            else:
                QMessageBox.critical(dialog, "Erro", msg)

        btn_ok.clicked.connect(_do_restore)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()
