"""
Ferramenta: Editor Seguro do Arquivo Hosts do Windows.
Gerenciamento de redirecionamentos locais, bloqueios de domínio, backup e flush DNS.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.hosts_editor.logic import (
    flush_dns_cache, list_hosts_backups, read_hosts_file, restore_hosts_backup, save_hosts_file
)


@register
class HostsEditorTool(Tool):
    id = "system.hosts_editor"
    name = "Editor do Arquivo Hosts"
    category = "Sistema"
    description = "Editor seguro do arquivo hosts do Windows com backup automático, alternância de hosts e Flush DNS"
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

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

        top_bar.addStretch()

        self.btn_flush_dns = QPushButton("Limpar Cache DNS (Flush DNS)")
        self.btn_flush_dns.clicked.connect(self._on_flush_dns)
        top_bar.addWidget(self.btn_flush_dns)

        layout.addLayout(top_bar)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Ativo", "Endereço IP", "Domínio / Hostname", "Comentário"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.table)

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
        self.table.blockSignals(True)
        self._entries = read_hosts_file()
        self.table.setRowCount(len(self._entries))

        for row, ent in enumerate(self._entries):
            # Checkbox de ativo
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Checked if ent.get("is_enabled", True) else Qt.Unchecked)
            self.table.setItem(row, 0, chk_item)

            ip_item = QTableWidgetItem(ent.get("ip", ""))
            self.table.setItem(row, 1, ip_item)

            host_item = QTableWidgetItem(ent.get("hostname", ""))
            self.table.setItem(row, 2, host_item)

            comm_item = QTableWidgetItem(ent.get("comment", ""))
            self.table.setItem(row, 3, comm_item)

        self.table.blockSignals(False)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            row = item.row()
            if 0 <= row < len(self._entries):
                self._entries[row]["is_enabled"] = (item.checkState() == Qt.Checked)

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
            self._entries.append({
                "ip": ip_val,
                "hostname": host_val,
                "comment": txt_comm.text().strip(),
                "is_enabled": True
            })
            dialog.accept()
            self._update_table_view()

        btn_ok.clicked.connect(_confirm)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()

    def _update_table_view(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._entries))
        for row, ent in enumerate(self._entries):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Checked if ent.get("is_enabled", True) else Qt.Unchecked)
            self.table.setItem(row, 0, chk_item)

            self.table.setItem(row, 1, QTableWidgetItem(ent.get("ip", "")))
            self.table.setItem(row, 2, QTableWidgetItem(ent.get("hostname", "")))
            self.table.setItem(row, 3, QTableWidgetItem(ent.get("comment", "")))
        self.table.blockSignals(False)

    def _on_remove_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Aviso", "Selecione uma linha para remover.")
            return

        row = selected[0].row()
        if 0 <= row < len(self._entries):
            del self._entries[row]
            self._update_table_view()

    def _on_save_hosts(self):
        # Sincroniza dados da tabela
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            ip = self.table.item(row, 1)
            host = self.table.item(row, 2)
            comm = self.table.item(row, 3)

            if row < len(self._entries):
                self._entries[row]["is_enabled"] = (chk.checkState() == Qt.Checked) if chk else True
                self._entries[row]["ip"] = ip.text().strip() if ip else ""
                self._entries[row]["hostname"] = host.text().strip() if host else ""
                self._entries[row]["comment"] = comm.text().strip() if comm else ""

        ok, msg = save_hosts_file(self._entries, create_backup=True)
        if ok:
            flush_dns_cache()
            QMessageBox.information(self, "Sucesso", f"{msg}\nO cache DNS também foi limpo automaticamente.")
            self._reload_hosts()
        else:
            if not is_admin():
                ans = QMessageBox.question(
                    self,
                    "Privilégios de Administrador Necessários",
                    f"{msg}\n\nPara salvar o arquivo hosts do sistema é obrigatório privilégios elevados. Deseja reiniciar a aplicação como Administrador?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)

    def _on_flush_dns(self):
        ok, msg = flush_dns_cache()
        if ok:
            QMessageBox.information(self, "Flush DNS", msg)
        else:
            QMessageBox.warning(self, "Flush DNS", msg)

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
        from PySide6.QtWidgets import QListWidget
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
            else:
                QMessageBox.critical(dialog, "Erro", msg)

        btn_ok.clicked.connect(_do_restore)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        dlg_layout.addLayout(btn_box)

        dialog.exec()
