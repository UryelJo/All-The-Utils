"""
Ferramenta: Desinstalador e Programas Instalados do Windows.
Visualização de programas instalados, pesquisa rápida e execução de desinstalação.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.uninstaller.logic import (
    list_installed_programs, run_uninstaller
)
from wintoolbox.ui.widgets.data_table import BackgroundLoader, Column, DataTableView, fmt_number
from wintoolbox.ui.widgets.tool_header import make_tool_header


def _fmt_install_date(value: str) -> str:
    """O registro guarda AAAAMMDD; alguns instaladores gravam já formatado."""
    v = (value or "").strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
    return v or "-"


COLUMNS = [
    Column("name", "Nome do Aplicativo", stretch=True, tooltip=True),
    Column("version", "Versão", width=120),
    Column("publisher", "Publicador", width=220, tooltip=True),
    Column("size_mb", "Tamanho (MB)", align="right", width=105,
           fmt=fmt_number(1, empty_if_zero=True)),
    Column("install_date", "Instalação", width=100, fmt=_fmt_install_date),
    Column("arch", "Origem", width=130),
]


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
        # Varre o registro uma vez em segundo plano; a pesquisa filtra localmente
        self._loader = BackgroundLoader(self._load_programs, self)
        self._loader.loaded.connect(self._on_loaded)
        self._build_ui()
        self._loader.request()

    @staticmethod
    def _load_programs():
        progs = list_installed_programs("")
        for p in progs:
            p["uid"] = f"{p['arch']}|{p['key_id']}"
        return progs

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_tool_header(self.tool))

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        top_bar.addWidget(QLabel("Pesquisar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Nome do aplicativo, publicador ou versão...")
        self.txt_filter.textChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._loader.request)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("Carregando...")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="uid", parent=self)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        layout.addWidget(self.table, stretch=1)

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

    def _on_loaded(self, programs):
        self.table.set_records(programs)
        self._update_count()

    def _on_filter_changed(self, text: str):
        self.table.proxy.set_text_filter(text)
        self._update_count()

    def _update_count(self):
        total = self.table.source_model.rowCount()
        shown = self.table.visible_count()
        self.lbl_count.setText(f"{total} programas instalados" if shown == total else f"{shown} de {total} programas")

    def _get_selected_program(self) -> Optional[dict]:
        return self.table.current_record()

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
