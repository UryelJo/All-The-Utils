"""
Ferramenta: Gerenciador de Processos do Windows.
Monitor em tempo real de CPU/RAM, busca, seleção múltipla com checkboxes, ícones e menu de contexto.
"""
import os
import subprocess
from typing import List, Optional
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.process_manager.logic import (
    ProcessSampler, get_process_details, terminate_multiple_processes, terminate_process
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import (
    BackgroundLoader, Column, DataTableView, bind_timer_to_visibility, fmt_number
)
from wintoolbox.ui.widgets.tool_header import make_tool_header

REFRESH_MS = 2000


@register
class ProcessManagerTool(Tool):
    id = "system.process_manager"
    name = "Gerenciador de Processos"
    category = "Sistema"
    description = "Monitoramento de processos em execução, consumo de CPU/RAM e finalização de tarefas em lote"
    keywords = ["processo", "taskmanager", "cpu", "memória", "ram", "finalizar", "kill", "tarefas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ProcessManagerView(self, parent)


COLUMNS = [
    Column("name", "Nome do Processo", width=270, tooltip=True, icon_key="exe", fallback_icon=True),
    Column("pid", "PID", align="right", width=75),
    Column("cpu_percent", "CPU (%)", align="right", width=85, fmt=fmt_number(1)),
    Column("memory_mb", "Memória (MB)", align="right", width=115, fmt=fmt_number(1)),
    Column("private_mb", "Privada (MB)", align="right", width=105, fmt=fmt_number(1)),
    Column("threads", "Threads", align="right", width=75),
    Column("handles", "Handles", align="right", width=80),
    Column("username", "Usuário", stretch=True),
]


class ProcessManagerView(QWidget):
    def __init__(self, tool: ProcessManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._sampler = ProcessSampler()
        self._loader = BackgroundLoader(self._sampler.sample, self)
        self._loader.loaded.connect(self._on_loaded)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._loader.request)
        bind_timer_to_visibility(self, self.timer, REFRESH_MS, on_show=self._loader.request)
        self._loader.request()

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
        self.txt_filter.setPlaceholderText("Nome do processo, PID ou usuário...")
        self.txt_filter.textChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.btn_clear_checks = QPushButton("Limpar Seleção")
        self.btn_clear_checks.setVisible(False)
        self.btn_clear_checks.clicked.connect(self._on_clear_checks)
        top_bar.addWidget(self.btn_clear_checks)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._loader.request)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("Carregando...")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)
        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="pid", parent=self, checkable=True)
        self.table.sortByColumn(3, Qt.DescendingOrder)  # memória, maior primeiro
        self.table.doubleClicked.connect(lambda _idx: self._on_view_details())
        self.table.checkedChanged.connect(self._on_checked_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        t = get_current_tokens()
        self.table.source_model.foreground = (
            lambda rec, key: t.status_warning if key == "cpu_percent" and rec["cpu_percent"] >= 25 else None
        )
        layout.addWidget(self.table, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_open_location = QPushButton("Abrir Local do Executável")
        self.btn_open_location.clicked.connect(self._on_open_location)
        bottom_bar.addWidget(self.btn_open_location)

        self.btn_details = QPushButton("Ver Detalhes")
        self.btn_details.clicked.connect(self._on_view_details)
        bottom_bar.addWidget(self.btn_details)

        bottom_bar.addStretch()

        self.btn_kill_tree = QPushButton("Finalizar Árvore de Processos")
        self.btn_kill_tree.clicked.connect(lambda: self._on_kill(tree=True))
        bottom_bar.addWidget(self.btn_kill_tree)

        self.btn_kill = QPushButton("Finalizar Processo")
        self.btn_kill.setProperty("class", "danger")
        self.btn_kill.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_kill.clicked.connect(lambda: self._on_kill(tree=False))
        bottom_bar.addWidget(self.btn_kill)

        layout.addLayout(bottom_bar)

    def _on_loaded(self, procs):
        self.table.set_records(procs)
        self._update_count()

    def _on_filter_changed(self, text: str):
        self.table.proxy.set_text_filter(text)
        self._update_count()

    def _on_select_all_toggled(self, checked: bool):
        self.table.set_all_visible_checked(checked)

    def _on_clear_checks(self):
        self.chk_select_all.blockSignals(True)
        self.chk_select_all.setChecked(False)
        self.chk_select_all.blockSignals(False)
        self.table.clear_checked()

    def _on_checked_changed(self, count: int):
        self.btn_clear_checks.setVisible(count > 0)
        if count > 0:
            self.btn_kill.setText(f"Finalizar Marcados ({count})")
            self.btn_kill_tree.setText(f"Finalizar Árvore dos Marcados ({count})")
        else:
            self.btn_kill.setText("Finalizar Processo")
            self.btn_kill_tree.setText("Finalizar Árvore de Processos")
        self._update_count()

    def _update_count(self):
        total = self.table.source_model.rowCount()
        shown = self.table.visible_count()
        checked = len(self.table.checked_records())
        base = f"{total} processos" if shown == total else f"{shown} de {total} processos"
        if checked > 0:
            base += f" ({checked} marcado(s))"
        self.lbl_count.setText(base)

    def _on_context_menu(self, pos: QPoint):
        rec = self.table.record_at_pos(pos)
        if not rec:
            return

        pid = int(rec["pid"])
        name = rec.get("name", f"PID {pid}")
        is_checked = self.table.is_record_checked(rec)
        checked_list = self.table.checked_records()

        menu = QMenu(self)
        act_toggle = menu.addAction("Desmarcar Processo" if is_checked else "Marcar Processo")
        menu.addSeparator()
        act_kill_one = menu.addAction(f"Finalizar '{name}' (PID {pid})")
        act_kill_tree_one = menu.addAction(f"Finalizar Árvore de '{name}'")

        act_kill_checked = None
        if len(checked_list) > 1 or (len(checked_list) == 1 and not is_checked):
            menu.addSeparator()
            act_kill_checked = menu.addAction(f"Finalizar Todos os Marcados ({len(checked_list)})")

        menu.addSeparator()
        act_open_loc = menu.addAction("Abrir Local do Executável")
        act_details = menu.addAction("Ver Detalhes")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_toggle:
            self.table.toggle_record_checked(rec)
        elif chosen == act_kill_one:
            self._kill_specific_pids([pid], [name], tree=False)
        elif chosen == act_kill_tree_one:
            self._kill_specific_pids([pid], [name], tree=True)
        elif act_kill_checked and chosen == act_kill_checked:
            self._on_kill(tree=False)
        elif chosen == act_open_loc:
            self._open_location_for_pid(pid)
        elif chosen == act_details:
            self._show_details_for_pid(pid)

    def _get_selected_pid(self) -> Optional[int]:
        rec = self.table.current_record()
        return int(rec["pid"]) if rec else None

    def _on_kill(self, tree: bool = False):
        targets = self.table.target_records()
        if not targets:
            QMessageBox.information(self, "Aviso", "Selecione ou marque pelo menos um processo na tabela para finalizar.")
            return

        pids = [int(r["pid"]) for r in targets]
        names = [str(r.get("name", r["pid"])) for r in targets]
        self._kill_specific_pids(pids, names, tree=tree)

    def _kill_specific_pids(self, pids: List[int], names: List[str], tree: bool = False):
        if len(pids) == 1:
            desc = f"a árvore do processo '{names[0]}' (PID {pids[0]})" if tree else f"o processo '{names[0]}' (PID {pids[0]})"
        else:
            sample = ", ".join(names[:4]) + ("..." if len(names) > 4 else "")
            desc = f"{len(pids)} processos selecionados ({sample})"

        confirm = QMessageBox.question(
            self,
            "Confirmar Encerramento",
            f"Deseja realmente finalizar {desc}?\nDados não salvos dos aplicativos podem ser perdidos.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        res = terminate_multiple_processes(pids, kill_tree=tree) if len(pids) > 1 else terminate_process(pids[0], kill_tree=tree)
        self.table.clear_checked()
        self.chk_select_all.blockSignals(True)
        self.chk_select_all.setChecked(False)
        self.chk_select_all.blockSignals(False)
        self._loader.request()

        if res.get("success") and not res.get("partial"):
            QMessageBox.information(self, "Sucesso", res["message"])
        elif res.get("access_denied") and not is_admin():
            prompt_elevation_dialog(self, tool_name=self.tool.name, reason=res["message"])
        elif res.get("partial"):
            QMessageBox.warning(self, "Encerramento Parcial", res["message"])
        else:
            QMessageBox.critical(self, "Erro", res["message"])

    def _on_open_location(self):
        pid = self._get_selected_pid()
        if not pid:
            QMessageBox.information(self, "Aviso", "Selecione um processo na tabela.")
            return
        self._open_location_for_pid(pid)

    def _open_location_for_pid(self, pid: int):
        details = get_process_details(pid)
        exe = details.get("executable")
        if exe and os.path.exists(exe):
            subprocess.Popen(f'explorer /select,"{exe}"')
        else:
            QMessageBox.warning(self, "Aviso", "Não foi possível localizar o caminho deste executável.")

    def _on_view_details(self):
        pid = self._get_selected_pid()
        if not pid:
            QMessageBox.information(self, "Aviso", "Selecione um processo na tabela.")
            return
        self._show_details_for_pid(pid)

    def _show_details_for_pid(self, pid: int):
        details = get_process_details(pid)
        if not details.get("success"):
            if details.get("access_denied") and not is_admin():
                prompt_elevation_dialog(self, tool_name=self.tool.name, reason=details.get("message", ""))
            else:
                QMessageBox.warning(self, "Aviso", details.get("message", "Falha ao obter detalhes."))
            return

        msg = (
            f"Nome: {details['name']}\n"
            f"PID: {details['pid']}\n"
            f"Executável: {details['executable']}\n"
            f"Linha de Comando: {details['cmdline']}\n"
            f"Pasta de Trabalho: {details['cwd']}\n"
            f"Threads: {details['num_threads']}\n"
            f"Memória RSS: {details['memory_rss_mb']} MB\n"
            f"Prioridade: {details['priority']}"
        )
        QMessageBox.information(self, f"Detalhes do Processo (PID {pid})", msg)
