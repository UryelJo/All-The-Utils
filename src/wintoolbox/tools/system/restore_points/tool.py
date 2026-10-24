"""
Interface gráfica do Gerenciador de Pontos de Restauração do Windows.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.restore_points.logic import (
    create_restore_point, launch_restore_wizard, list_restore_points
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.restore_points.ui")


@register
class RestorePointsTool(Tool):
    id = "system.restore_points"
    name = "Pontos de Restauração do Windows"
    category = "Sistema"
    description = "Consulta, criação rápida e inicialização do assistente de restauração do sistema"
    keywords = ["restauracao", "ponto", "recovery", "rstrui", "backup", "sistema", "reverter", "checkpoint"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RestorePointsView(self, parent)


class RestorePointsView(QWidget):
    def __init__(self, tool: RestorePointsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        # Grupo: Criar Novo Ponto
        create_box = QGroupBox("Criar Novo Ponto de Restauração")
        create_lay = QHBoxLayout(create_box)
        create_lay.setContentsMargins(12, 12, 12, 12)
        create_lay.setSpacing(8)

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ex: Antes da instalação de novo driver ou software...")
        create_lay.addWidget(self.txt_desc, stretch=1)

        self.btn_create = QPushButton("Criar Ponto Agora")
        self.btn_create.setProperty("accent", True)
        self.btn_create.clicked.connect(self._create_point_async)
        create_lay.addWidget(self.btn_create)
        layout.addWidget(create_box)

        # Barra de ações da lista
        actions_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._load_points_async)
        actions_bar.addWidget(self.btn_refresh)

        self.btn_launch_wizard = QPushButton("Abrir Assistente de Restauração (rstrui.exe)")
        self.btn_launch_wizard.clicked.connect(self._launch_wizard)
        actions_bar.addWidget(self.btn_launch_wizard)

        actions_bar.addStretch()
        self.lbl_status = QLabel("Consultando pontos...")
        actions_bar.addWidget(self.lbl_status)
        layout.addLayout(actions_bar)

        # Tabela de pontos
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Data e Hora", "Descrição", "Tipo do Ponto", "Sequência"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, stretch=1)

        self._load_points_async()

    def _load_points_async(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Consultando pontos de restauração...")

        def _worker():
            return list_restore_points()

        def _on_done(points: List[Dict[str, Any]]):
            self.btn_refresh.setEnabled(True)
            self.table.setRowCount(len(points))
            for row, p in enumerate(points):
                self.table.setItem(row, 0, QTableWidgetItem(p["creation_time"]))
                self.table.setItem(row, 1, QTableWidgetItem(p["description"]))
                self.table.setItem(row, 2, QTableWidgetItem(p["type"]))
                self.table.setItem(row, 3, QTableWidgetItem(str(p["sequence_number"])))

            if points:
                self.lbl_status.setText(f"{len(points)} ponto(s) de restauração encontrado(s).")
            else:
                self.lbl_status.setText("Nenhum ponto de restauração encontrado na máquina.")

        def _on_error(err):
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText("Erro ao listar pontos.")
            show_toast(self, "Falha na consulta de pontos de restauração", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _create_point_async(self) -> None:
        desc = self.txt_desc.text().strip()
        if not desc:
            show_toast(self, "Digite uma descrição para o ponto de restauração.", is_error=True)
            return

        self.btn_create.setEnabled(False)
        self.lbl_status.setText("Criando ponto de restauração (pode levar alguns segundos)...")

        def _worker():
            return create_restore_point(desc)

        def _on_done(result):
            success, msg = result
            self.btn_create.setEnabled(True)
            if success:
                self.txt_desc.clear()
                show_toast(self, "Ponto de restauração criado com sucesso!")
                self._load_points_async()
            else:
                self.lbl_status.setText("Falha na criação do ponto.")
                show_toast(self, msg, is_error=True)

        def _on_error(err):
            self.btn_create.setEnabled(True)
            self.lbl_status.setText("Erro inesperado.")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _launch_wizard(self) -> None:
        ok, msg = launch_restore_wizard()
        if ok:
            show_toast(self, msg)
        else:
            show_toast(self, msg, is_error=True)
