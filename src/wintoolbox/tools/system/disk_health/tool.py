"""
Interface gráfica do Diagnóstico de Saúde de Discos e SSDs (SMART).
Integrada ao Monitor de Hardware com diagnóstico explicativo e tooltips detalhados.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.disk_health.logic import (
    SMART_PARAMETER_TOOLTIPS,
    build_disk_health_diagnosis,
    get_disks_health_info,
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.disk_health.ui")


class DiskHealthTool(Tool):
    id = "system.disk_health"
    name = "Saúde do Disco e SSD (SMART)"
    category = "Sistema"
    description = "Diagnóstico detalhado de integridade, temperatura, desgaste de SSD e contadores de erro"
    keywords = ["disco", "ssd", "smart", "saude", "temperatura", "desgaste", "nvme", "vida util", "hd"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DiskHealthView(self, parent)


class DiskHealthView(QWidget):
    def __init__(
        self,
        tool: Optional[DiskHealthTool] = None,
        parent: Optional[QWidget] = None,
        embedded: bool = False,
        auto_load: bool = True,
    ):
        super().__init__(parent)
        self.tool = tool or DiskHealthTool()

        layout = QVBoxLayout(self)
        if embedded:
            layout.setContentsMargins(8, 10, 8, 8)
        else:
            layout.setContentsMargins(20, 20, 20, 20)
            layout.addWidget(ToolHeader(self.tool.name, self.tool.description))
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Atualizar Diagnóstico SMART")
        self.btn_refresh.setProperty("accent", True)
        self.btn_refresh.clicked.connect(self._load_disks_async)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_status = QLabel("Passe o mouse sobre qualquer parâmetro para ver a explicação técnica detalhada.")
        self.lbl_status.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()
        layout.addLayout(top_bar)

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

        if auto_load:
            self._load_disks_async()

    def _load_disks_async(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Lendo contadores SMART e status de integridade dos discos...")

        def _worker():
            return get_disks_health_info()

        def _on_done(disks: List[Dict[str, Any]]):
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText(
                f"{len(disks)} unidade(s) física(s) analisada(s). Passe o mouse nos parâmetros para detalhes."
            )
            self._render_disk_cards(disks)

        def _on_error(_err):
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText("Erro ao consultar discos.")
            show_toast(self, "Falha na leitura dos discos", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    @staticmethod
    def _add_param_pair(grid: QGridLayout, row: int, col_start: int, label_txt: str, val_txt: str, tooltip: str):
        lbl_k = QLabel(label_txt)
        lbl_v = QLabel(f"<b>{val_txt}</b>")
        if tooltip:
            lbl_k.setToolTip(tooltip)
            lbl_v.setToolTip(tooltip)
        grid.addWidget(lbl_k, row, col_start)
        grid.addWidget(lbl_v, row, col_start + 1)

    def _render_disk_cards(self, disks: List[Dict[str, Any]]) -> None:
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
            card.setProperty("class", "card")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(16, 14, 16, 14)
            card_lay.setSpacing(10)

            header_lay = QHBoxLayout()
            title_lbl = QLabel(f"<b>{d['name']}</b> ({d['size_str']})")
            title_lbl.setStyleSheet("font-size: 14px;")
            header_lay.addWidget(title_lbl)
            header_lay.addStretch()

            health = str(d.get("health_status", "Healthy")).upper()
            diagnosis = d.get("diagnosis_summary") or build_disk_health_diagnosis(d)

            if "HEALTHY" in health or "OK" in health:
                badge_text = "Saudável"
                badge_style = "background-color: #107c41; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold;"
            elif "WARN" in health:
                badge_text = "Atenção"
                badge_style = "background-color: #d83b01; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold;"
            else:
                badge_text = "Crítico"
                badge_style = "background-color: #a80000; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold;"

            status_badge = QLabel(badge_text)
            status_badge.setStyleSheet(badge_style)
            status_badge.setToolTip(diagnosis)
            header_lay.addWidget(status_badge)
            card_lay.addLayout(header_lay)

            # Justificativa explícita do diagnóstico
            lbl_diag = QLabel(diagnosis)
            lbl_diag.setWordWrap(True)
            lbl_diag.setProperty("class", "secondary")
            lbl_diag.setToolTip("Justificativa detalhada calculada com base nos sensores SMART e contadores de erro.")
            card_lay.addWidget(lbl_diag)

            # Grid de informações técnicas com tooltips
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(6)

            self._add_param_pair(
                grid, 0, 0, "Tipo de Mídia:", str(d.get("media_type", "-")),
                SMART_PARAMETER_TOOLTIPS["media_type"]
            )
            self._add_param_pair(
                grid, 0, 2, "Barramento:", str(d.get("bus_type", "-")),
                SMART_PARAMETER_TOOLTIPS["bus_type"]
            )

            temp = d.get("temperature_c")
            temp_str = f"{temp} °C" if temp is not None else "Não disponível (Sensor não exposto)"
            self._add_param_pair(
                grid, 1, 0, "Temperatura:", temp_str,
                SMART_PARAMETER_TOOLTIPS["temperature_c"]
            )

            poh = d.get("power_on_hours")
            if poh is not None:
                days = poh // 24
                poh_str = f"{poh} horas (~{days} dias ligado)"
            else:
                poh_str = "Não disponível"
            self._add_param_pair(
                grid, 1, 2, "Tempo em Atividade:", poh_str,
                SMART_PARAMETER_TOOLTIPS["power_on_hours"]
            )

            r_err = d.get("read_errors", 0)
            w_err = d.get("write_errors", 0)
            self._add_param_pair(
                grid, 2, 0, "Erros Leitura / Escrita:", f"{r_err} / {w_err}",
                SMART_PARAMETER_TOOLTIPS["errors"]
            )
            self._add_param_pair(
                grid, 2, 2, "Status Operacional:", str(d.get("operational_status", "OK")),
                SMART_PARAMETER_TOOLTIPS["operational_status"]
            )

            card_lay.addLayout(grid)

            wear = d.get("wear_percent")
            if wear is not None:
                wear_box = QGroupBox("Desgaste e Vida Útil Estimada do SSD")
                wear_box.setToolTip(SMART_PARAMETER_TOOLTIPS["wear_percent"])
                wear_lay = QVBoxLayout(wear_box)
                remaining_life = max(0, 100 - int(wear))
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(remaining_life)
                bar.setFormat(f"Vida Útil Restante: {remaining_life}% (Desgaste NAND: {wear}%)")
                bar.setToolTip(SMART_PARAMETER_TOOLTIPS["wear_percent"])
                wear_lay.addWidget(bar)
                card_lay.addWidget(wear_box)

            self.cards_layout.insertWidget(idx, card)
