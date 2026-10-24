"""
Interface gráfica do Diagnóstico de Saúde de Discos e SSDs (SMART).
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.disk_health.logic import get_disks_health_info
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.disk_health.ui")


@register
class DiskHealthTool(Tool):
    id = "system.disk_health"
    name = "Saúde do Disco e SSD (SMART)"
    category = "Sistema"
    description = "Diagnóstico detalhado de integridade, temperatura, desgaste de SSD e contadores de erro"
    keywords = ["disco", "ssd", "smart", "saude", "temperatura", "desgaste", "nvme", "vida util", "hd"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DiskHealthView(self, parent)


class DiskHealthView(QWidget):
    def __init__(self, tool: DiskHealthTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        top_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Atualizar Diagnósticos")
        self.btn_refresh.setProperty("accent", True)
        self.btn_refresh.clicked.connect(self._load_disks_async)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_status = QLabel("Pronto para escanear discos.")
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Área de rolagem para os cartões de disco
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Dispara carregamento inicial
        self._load_disks_async()

    def _load_disks_async(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Lendo contadores SMART e status dos discos...")

        def _worker():
            return get_disks_health_info()

        def _on_done(disks: List[Dict[str, Any]]):
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText(f"{len(disks)} unidade(s) de armazenamento detectada(s).")
            self._render_disk_cards(disks)

        def _on_error(err):
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText("Erro ao consultar discos.")
            show_toast(self, "Falha na leitura dos discos", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _render_disk_cards(self, disks: List[Dict[str, Any]]) -> None:
        # Limpa cartões anteriores
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not disks:
            empty_lbl = QLabel("Nenhuma unidade de disco físico foi retornada pelo sistema.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self.cards_layout.insertWidget(0, empty_lbl)
            return

        for idx, d in enumerate(disks):
            card = QFrame()
            card.setObjectName("Card")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(16, 16, 16, 16)
            card_lay.setSpacing(10)

            # Cabeçalho do disco
            header_lay = QHBoxLayout()
            title_lbl = QLabel(f"<b>{d['name']}</b> ({d['size_str']})")
            title_lbl.setStyleSheet("font-size: 14px;")
            header_lay.addWidget(title_lbl)

            header_lay.addStretch()

            # Status de integridade
            health = str(d.get("health_status", "Healthy")).upper()
            if "HEALTHY" in health or "OK" in health:
                badge_text = "Saudável"
                badge_style = "background-color: #107c41; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;"
            elif "WARN" in health:
                badge_text = "Atenção"
                badge_style = "background-color: #d83b01; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;"
            else:
                badge_text = "Crítico"
                badge_style = "background-color: #a80000; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;"

            status_badge = QLabel(badge_text)
            status_badge.setStyleSheet(badge_style)
            header_lay.addWidget(status_badge)
            card_lay.addLayout(header_lay)

            # Grid de informações técnicas
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(6)

            grid.addWidget(QLabel("Tipo de Mídia:"), 0, 0)
            grid.addWidget(QLabel(f"<b>{d['media_type']}</b>"), 0, 1)

            grid.addWidget(QLabel("Barramento:"), 0, 2)
            grid.addWidget(QLabel(f"<b>{d['bus_type']}</b>"), 0, 3)

            # Temperatura
            temp = d.get("temperature_c")
            temp_str = f"{temp} °C" if temp is not None else "Não disponível"
            grid.addWidget(QLabel("Temperatura:"), 1, 0)
            grid.addWidget(QLabel(f"<b>{temp_str}</b>"), 1, 1)

            # Horas ligado
            poh = d.get("power_on_hours")
            if poh is not None:
                days = poh // 24
                poh_str = f"{poh} horas (~{days} dias)"
            else:
                poh_str = "Não disponível"
            grid.addWidget(QLabel("Tempo em Atividade:"), 1, 2)
            grid.addWidget(QLabel(f"<b>{poh_str}</b>"), 1, 3)

            # Erros de Leitura / Escrita
            r_err = d.get("read_errors", 0)
            w_err = d.get("write_errors", 0)
            grid.addWidget(QLabel("Erros Leitura / Escrita:"), 2, 0)
            grid.addWidget(QLabel(f"<b>{r_err} / {w_err}</b>"), 2, 1)

            grid.addWidget(QLabel("Status Operacional:"), 2, 2)
            grid.addWidget(QLabel(f"<b>{d['operational_status']}</b>"), 2, 3)

            card_lay.addLayout(grid)

            # Vida útil / Desgaste de SSD (se for SSD)
            wear = d.get("wear_percent")
            if wear is not None:
                wear_box = QGroupBox("Desgaste e Vida Útil do SSD")
                wear_lay = QVBoxLayout(wear_box)
                remaining_life = max(0, 100 - wear)
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(remaining_life)
                bar.setFormat(f"Vida Útil Restante: {remaining_life}% (Desgaste: {wear}%)")
                wear_lay.addWidget(bar)
                card_lay.addWidget(wear_box)

            self.cards_layout.insertWidget(idx, card)
