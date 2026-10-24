"""
Interface gráfica de Controle de Privacidade e Debloat do Windows.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.privacy.logic import (
    get_all_privacy_statuses, set_privacy_item
)
from wintoolbox.tools.system.restore_points.logic import create_restore_point
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.privacy.ui")


@register
class PrivacyTool(Tool):
    id = "system.privacy"
    name = "Privacidade e Debloat do Windows"
    category = "Sistema"
    description = "Desativação de telemetria diagnóstica, anúncios, sugestões do sistema, Copilot e análise de IA"
    keywords = ["privacidade", "telemetria", "debloat", "copilot", "recall", "anuncios", "rastreamento", "windows 11"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PrivacyView(self, parent)


class PrivacyView(QWidget):
    def __init__(self, tool: PrivacyTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._checkbox_map: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Barra de atalhos rápidos
        bar = QHBoxLayout()
        self.btn_select_all = QPushButton("Marcar Todas as Proteções")
        self.btn_select_all.clicked.connect(self._select_all)
        bar.addWidget(self.btn_select_all)

        self.btn_reload = QPushButton("Recarregar Status Atual")
        self.btn_reload.clicked.connect(self._load_statuses)
        bar.addWidget(self.btn_reload)

        bar.addStretch()
        layout.addLayout(bar)

        # Scroll com itens de privacidade
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self.container_lay = QVBoxLayout(container)
        self.container_lay.setContentsMargins(0, 0, 0, 0)
        self.container_lay.setSpacing(8)

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Rodapé de aplicação
        footer = QHBoxLayout()
        self.chk_create_restore = QCheckBox("Criar ponto de restauração do sistema antes de aplicar")
        self.chk_create_restore.setChecked(True)
        footer.addWidget(self.chk_create_restore)

        footer.addStretch()

        self.btn_apply = QPushButton("Aplicar Ajustes Selecionados")
        self.btn_apply.setProperty("accent", True)
        self.btn_apply.clicked.connect(self._apply_changes_async)
        footer.addWidget(self.btn_apply)

        layout.addLayout(footer)

        self._load_statuses()

    def _load_statuses(self) -> None:
        # Limpa widgets anteriores
        while self.container_lay.count() > 0:
            item = self.container_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkbox_map.clear()

        statuses = get_all_privacy_statuses()
        for s in statuses:
            card = QFrame()
            card.setObjectName("Card")
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            card_lay.setSpacing(12)

            chk = QCheckBox()
            chk.setChecked(s["is_protected"])
            self._checkbox_map[s["id"]] = chk
            card_lay.addWidget(chk)

            text_lay = QVBoxLayout()
            text_lay.setSpacing(4)
            lbl_name = QLabel(f"<b>{s['name']}</b>")
            lbl_name.setStyleSheet("font-size: 13px;")
            lbl_desc = QLabel(s["desc"])
            lbl_desc.setStyleSheet("color: #888888;")
            lbl_desc.setWordWrap(True)
            text_lay.addWidget(lbl_name)
            text_lay.addWidget(lbl_desc)

            card_lay.addLayout(text_lay, stretch=1)
            self.container_lay.addWidget(card)

        self.container_lay.addStretch()

    def _select_all(self) -> None:
        for chk in self._checkbox_map.values():
            chk.setChecked(True)

    def _apply_changes_async(self) -> None:
        self.btn_apply.setEnabled(False)
        needs_restore = self.chk_create_restore.isChecked()
        targets = {item_id: chk.isChecked() for item_id, chk in self._checkbox_map.items()}

        def _worker():
            messages = []
            if needs_restore:
                ok, msg = create_restore_point("Antes de aplicar privacidade/debloat")
                messages.append(msg)

            for it_id, enabled in targets.items():
                _, m = set_privacy_item(it_id, enabled)
                messages.append(m)
            return messages

        def _on_done(msgs):
            self.btn_apply.setEnabled(True)
            show_toast(self, "Ajustes de privacidade aplicados com sucesso!")
            self._load_statuses()

        def _on_error(err):
            self.btn_apply.setEnabled(True)
            show_toast(self, f"Erro ao aplicar ajustes: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
