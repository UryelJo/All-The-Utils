"""
Interface gráfica da Central de Reparos do Windows.
"""
from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.repair_center.logic import (
    clear_icon_and_thumbnail_cache, flush_network_stack,
    repair_print_spooler, reset_microsoft_store, reset_windows_update
)
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.repair_center.ui")


@register
class RepairCenterTool(Tool):
    id = "system.repair_center"
    name = "Central de Reparos do Windows"
    category = "Sistema"
    description = "Correção rápida de fila de impressão travada, cache de ícones, Windows Update e rede"
    keywords = ["reparo", "conserto", "spooler", "impressora", "icones", "cache", "windows update", "store", "wsreset"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RepairCenterView(self, parent)


class RepairCenterView(QWidget):
    def __init__(self, tool: RepairCenterTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(10)

        repairs = [
            (
                "Destravar Fila de Impressão (Spooler)",
                "Interrompe o serviço de spooler, remove documentos presos em buffer e reinicia o serviço.",
                repair_print_spooler
            ),
            (
                "Reconstruir Cache de Ícones e Miniaturas",
                "Corrige ícones brancos, genéricos ou miniaturas corrompidas reiniciando o cache do Explorer.",
                clear_icon_and_thumbnail_cache
            ),
            (
                "Resetar Componentes do Windows Update",
                "Para serviços de atualização e remove pacotes de download corrompidos em SoftwareDistribution.",
                reset_windows_update
            ),
            (
                "Redefinir Cache da Microsoft Store (wsreset)",
                "Limpa o cache corrompido da Microsoft Store que impede download ou atualização de apps.",
                reset_microsoft_store
            ),
            (
                "Redefinir Pilha de Rede e Cache DNS",
                "Executa o flush de DNS e restaura o catálogo Winsock e pilha TCP/IP do Windows.",
                flush_network_stack
            )
        ]

        for title, desc, fn in repairs:
            card = QFrame()
            card.setObjectName("Card")
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            card_lay.setSpacing(12)

            text_lay = QVBoxLayout()
            text_lay.setSpacing(4)
            lbl_t = QLabel(f"<b>{title}</b>")
            lbl_t.setStyleSheet("font-size: 13px;")
            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("color: #888888;")
            lbl_d.setWordWrap(True)
            text_lay.addWidget(lbl_t)
            text_lay.addWidget(lbl_d)
            card_lay.addLayout(text_lay, stretch=1)

            btn = QPushButton("Executar Reparo")
            btn.setProperty("accent", True)
            btn.setFixedWidth(140)
            btn.clicked.connect(lambda _, f=fn, t=title: self._execute_repair(t, f))
            card_lay.addWidget(btn)

            c_lay.addWidget(card)

        c_lay.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        self.log_panel = LogPanelWidget(title="Registro de Execução de Reparos")
        self.log_panel.setMaximumHeight(160)
        layout.addWidget(self.log_panel)

    def _execute_repair(self, name: str, func: Callable[[], Any]) -> None:
        self.log_panel.append_line(f"Iniciando: {name}...")

        def _worker():
            return func()

        def _on_done(result):
            success, msg = result
            if success:
                self.log_panel.append_line(f"Sucesso: {msg}\n")
                show_toast(self, "Reparo concluído com sucesso!")
            else:
                self.log_panel.append_line(f"Aviso/Falha: {msg}\n")
                show_toast(self, msg, is_error=True)

        def _on_error(err):
            self.log_panel.append_line(f"Erro: {err}\n")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
