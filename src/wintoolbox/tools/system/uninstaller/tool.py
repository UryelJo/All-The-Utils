"""
Ferramenta: Desinstalador e Programas Instalados do Windows.
Visualização de programas instalados, pesquisa rápida e execução de desinstalação.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.uninstaller.logic import (
    list_installed_programs, run_uninstaller
)


@register
class UninstallerTool(Tool):
    id = "system.uninstaller"
    name = "Programas Instalados e Desinstalador"
    category = "Sistema"
    description = "Visualização de todos os aplicativos instalados no Windows, tamanho em disco e desinstalação"
    keywords = ["desinstalador", "uninstall", "programas", "aplicativos", "apps", "painel", "remover"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return UninstallerView(self, parent)


class UninstallerView(QWidget):
    def __init__(self, tool: UninstallerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._raw_programs = []
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        top_bar.addWidget(QLabel("Pesquisar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtrar por nome do aplicativo ou publicador...")
        self.txt_filter.textChanged.connect(self._refresh_list)
        top_bar.addWidget(self.txt_filter)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._refresh_list)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("0 programas")
        self.lbl_count.setStyleSheet("color: #888890; font-weight: 500;")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Nome do Aplicativo", "Versão", "Publicador", "Tamanho (MB)", "Data de Instalação"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Barra Inferior
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_copy_cmd = QPushButton("Copiar Comando de Desinstalação")
        self.btn_copy_cmd.clicked.connect(self._on_copy_cmd)
        bottom_bar.addWidget(self.btn_copy_cmd)

        bottom_bar.addStretch()

        self.btn_quiet_uninstall = QPushButton("Desinstalação Silenciosa")
        self.btn_quiet_uninstall.clicked.connect(lambda: self._on_uninstall(quiet=True))
        bottom_bar.addWidget(self.btn_quiet_uninstall)

        self.btn_uninstall = QPushButton("Desinstalar Aplicativo")
        self.btn_uninstall.setProperty("class", "danger")
        self.btn_uninstall.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_uninstall.clicked.connect(lambda: self._on_uninstall(quiet=False))
        bottom_bar.addWidget(self.btn_uninstall)

        layout.addLayout(bottom_bar)

    def _refresh_list(self):
        query = self.txt_filter.text()
        self._raw_programs = list_installed_programs(query)

        self.table.setRowCount(len(self._raw_programs))
        for row, p in enumerate(self._raw_programs):
            self.table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(p["version"]))
            self.table.setItem(row, 2, QTableWidgetItem(p["publisher"]))

            sz_str = f"{p['size_mb']:.1f}" if p["size_mb"] > 0 else "-"
            sz_item = QTableWidgetItem(sz_str)
            sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, sz_item)

            self.table.setItem(row, 4, QTableWidgetItem(p["install_date"]))

        self.lbl_count.setText(f"{len(self._raw_programs)} programas instalados")

    def _get_selected_program(self) -> Optional[dict]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self._raw_programs):
            return self._raw_programs[row]
        return None

    def _on_uninstall(self, quiet: bool = False):
        prog = self._get_selected_program()
        if not prog:
            QMessageBox.information(self, "Aviso", "Selecione um programa para desinstalar.")
            return

        cmd = prog.get("quiet_uninstall_string") if quiet else prog.get("uninstall_string")
        if not cmd and quiet:
            cmd = prog.get("uninstall_string")

        if not cmd:
            QMessageBox.warning(self, "Aviso", "Nenhum comando de desinstalação registrado para este programa.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar Desinstalação",
            f"Deseja iniciar o processo de desinstalação de '{prog['name']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        ok, msg = run_uninstaller(cmd)
        if ok:
            QMessageBox.information(self, "Desinstalador", msg)
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _on_copy_cmd(self):
        prog = self._get_selected_program()
        if not prog:
            QMessageBox.information(self, "Aviso", "Selecione um programa na lista.")
            return

        cmd = prog.get("uninstall_string") or prog.get("quiet_uninstall_string") or ""
        if cmd:
            QApplication.clipboard().setText(cmd)
            QMessageBox.information(self, "Copiado", "Comando de desinstalação copiado para a área de transferência.")
        else:
            QMessageBox.warning(self, "Aviso", "Nenhum comando disponível.")
