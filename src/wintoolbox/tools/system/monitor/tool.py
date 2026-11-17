"""
Ferramenta: Monitor de Hardware, Saúde de Disco (SMART) e Inventário Completo do Sistema.
Interface unificada em abas com métricas em tempo real, diagnóstico SMART e especificações físicas.
"""
from typing import Optional
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QSizePolicy, QTabWidget, QTableWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.disk_health.tool import DiskHealthTool, DiskHealthView
from wintoolbox.tools.system.hardware_info.tool import HardwareInfoTool
from wintoolbox.ui.widgets.data_table import BackgroundLoader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, batch_table_update, enable_sorting_on_table
)
from .logic import SystemMetricsSnapshot, collect_hardware_metrics

_log = get_logger("monitor")


@register
class HardwareMonitorTool(Tool):
    id = "system.monitor"
    name = "Monitor de Hardware"
    category = "Sistema"
    description = "Monitor em tempo real (CPU, RAM e Discos), Saúde SMART de Discos/SSDs e Inventário de Hardware"
    keywords = [
        "hardware", "monitor", "cpu", "ram", "memória", "disco", "armazenamento",
        "desempenho", "smart", "ssd", "saude", "temperatura", "gpu", "placa-mae", "bios"
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HardwareMonitorView(self, parent)


class HardwareMonitorView(QWidget):
    def __init__(self, tool: HardwareMonitorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._hw_info_tool = HardwareInfoTool()
        self._smart_loaded = False
        self._hw_info_loaded = False
        self._build_ui()

        # Timer para atualização periódica a cada 2 segundos
        self._loader = BackgroundLoader(collect_hardware_metrics, self)
        self._loader.loaded.connect(self._apply_metrics)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._loader.request)
        from wintoolbox.core.elevation import is_headless_or_test
        if not is_headless_or_test():
            self.timer.start(2000)
            self._loader.request()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 16)
        root_layout.setSpacing(10)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        root_layout.addWidget(lbl_desc)

        self.tabs = QTabWidget()

        # Aba 1: Monitor em Tempo Real
        tab_realtime = self._build_realtime_tab()
        self.tabs.addTab(tab_realtime, "Monitor em Tempo Real")

        # Aba 2: Saúde do Disco e SSD (SMART)
        self.disk_health_view = DiskHealthView(DiskHealthTool(), self, embedded=True, auto_load=False)
        self.tabs.addTab(self.disk_health_view, "Saúde do Disco e SSD (SMART)")

        # Aba 3: Informações Detalhadas de Hardware
        self.hardware_info_view = self._hw_info_tool.build_ui(auto_load=False)
        self.tabs.addTab(self.hardware_info_view, "Informações de Hardware")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        root_layout.addWidget(self.tabs, stretch=1)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and not self._smart_loaded:
            self._smart_loaded = True
            self.disk_health_view._load_disks_async()
        elif index == 2 and not self._hw_info_loaded:
            self._hw_info_loaded = True
            self._hw_info_tool._load_hardware_info()

    def _build_realtime_tab(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        # Cartão de Métricas: CPU e RAM lado a lado
        row_metrics = QHBoxLayout()
        row_metrics.setSpacing(12)

        # Card CPU
        card_cpu = QFrame()
        card_cpu.setProperty("class", "card")
        layout_cpu = QVBoxLayout(card_cpu)
        layout_cpu.setContentsMargins(14, 10, 14, 10)
        layout_cpu.setSpacing(6)

        lbl_cpu_title = QLabel("Processador (CPU)")
        lbl_cpu_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        lbl_cpu_title.setFixedHeight(20)
        layout_cpu.addWidget(lbl_cpu_title)

        self.lbl_cpu_detail = QLabel("Uso: 0% | Núcleos lógicos: -")
        self.lbl_cpu_detail.setProperty("class", "secondary")
        self.lbl_cpu_detail.setFixedHeight(18)
        layout_cpu.addWidget(self.lbl_cpu_detail)

        self.prog_cpu = QProgressBar()
        self.prog_cpu.setRange(0, 100)
        self.prog_cpu.setValue(0)
        layout_cpu.addWidget(self.prog_cpu)

        row_metrics.addWidget(card_cpu, stretch=1)

        # Card RAM
        card_ram = QFrame()
        card_ram.setProperty("class", "card")
        layout_ram = QVBoxLayout(card_ram)
        layout_ram.setContentsMargins(14, 10, 14, 10)
        layout_ram.setSpacing(6)

        lbl_ram_title = QLabel("Memória RAM")
        lbl_ram_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        lbl_ram_title.setFixedHeight(20)
        layout_ram.addWidget(lbl_ram_title)

        self.lbl_ram_detail = QLabel("Uso: 0.0 GB / 0.0 GB (0%)")
        self.lbl_ram_detail.setProperty("class", "secondary")
        self.lbl_ram_detail.setFixedHeight(18)
        layout_ram.addWidget(self.lbl_ram_detail)

        self.prog_ram = QProgressBar()
        self.prog_ram.setRange(0, 100)
        self.prog_ram.setValue(0)
        layout_ram.addWidget(self.prog_ram)

        row_metrics.addWidget(card_ram, stretch=1)
        layout.addLayout(row_metrics)

        # Cartão de Armazenamento / Discos (com espaçamento compacto no título)
        card_disks = QFrame()
        card_disks.setProperty("class", "card")
        layout_disks = QVBoxLayout(card_disks)
        layout_disks.setContentsMargins(14, 10, 14, 10)
        layout_disks.setSpacing(6)

        lbl_disks_title = QLabel("Armazenamento e Unidades de Disco")
        lbl_disks_title.setStyleSheet("font-weight: 600; font-size: 13px; margin: 0px; padding: 0px;")
        lbl_disks_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lbl_disks_title.setFixedHeight(20)
        layout_disks.addWidget(lbl_disks_title)

        self.table_disks = QTableWidget(0, 5)
        self.table_disks.setHorizontalHeaderLabels([
            "Unidade", "Sistema", "Total", "Espaço Livre", "Uso (%)"
        ])
        self.table_disks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_disks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_disks.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_disks.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_disks.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_disks.verticalHeader().setVisible(False)
        self.table_disks.setMinimumHeight(140)
        enable_sorting_on_table(self.table_disks)
        layout_disks.addWidget(self.table_disks, stretch=1)

        layout.addWidget(card_disks, stretch=1)
        return content

    def _update_metrics(self):
        self._loader.request()

    def _apply_metrics(self, m: SystemMetricsSnapshot):
        try:
            cpu_val = int(m.cpu_percent)
            self.lbl_cpu_detail.setText(f"Uso: {cpu_val}% | Núcleos lógicos: {m.cpu_count}")
            self.prog_cpu.setValue(cpu_val)

            ram_val = int(m.mem_percent)
            self.lbl_ram_detail.setText(
                f"Uso: {m.mem_used_gb} GB de {m.mem_total_gb} GB ({ram_val}%)"
            )
            self.prog_ram.setValue(ram_val)

            with batch_table_update(self.table_disks):
                self.table_disks.setRowCount(len(m.disks))
                for row, d in enumerate(m.disks):
                    self.table_disks.setItem(row, 0, SmartTableWidgetItem(f"{d.device} ({d.mountpoint})", user_data=d))
                    self.table_disks.setItem(row, 1, SmartTableWidgetItem(d.fstype))
                    self.table_disks.setItem(row, 2, SmartTableWidgetItem(f"{d.total_gb} GB", sort_value=d.total_gb))
                    self.table_disks.setItem(row, 3, SmartTableWidgetItem(f"{d.free_gb} GB livre", sort_value=d.free_gb))

                    bar = self.table_disks.cellWidget(row, 4)
                    if not isinstance(bar, QProgressBar):
                        bar = QProgressBar()
                        bar.setRange(0, 100)
                        self.table_disks.setCellWidget(row, 4, bar)
                    bar.setValue(int(d.percent))
                    bar.setFormat(f"{d.percent}%")
        except Exception:
            _log.exception("Falha ao atualizar métricas do monitor")

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.timer.start(2000)
        self._update_metrics()
        super().showEvent(event)
