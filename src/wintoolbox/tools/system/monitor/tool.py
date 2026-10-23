"""
Ferramenta: Monitor de Hardware e Recursos do Sistema.
Interface com atualização em tempo real de CPU, Memória e Discos.
"""
from typing import Optional
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.system_info import get_realtime_metrics

@register
class HardwareMonitorTool(Tool):
    id = "system.monitor"
    name = "Monitor de Hardware"
    category = "Sistema"
    description = "Acompanhamento em tempo real do consumo de processador, memória RAM e discos"
    keywords = ["hardware", "monitor", "cpu", "ram", "memória", "disco", "armazenamento", "desempenho"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HardwareMonitorView(self, parent)

class HardwareMonitorView(QWidget):
    def __init__(self, tool: HardwareMonitorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

        # Timer para atualização periódica a cada 2 segundos
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(2000)
        self._update_metrics()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Cartão de Métricas: CPU e RAM lado a lado
        row_metrics = QHBoxLayout()
        row_metrics.setSpacing(12)

        # Card CPU
        card_cpu = QFrame()
        card_cpu.setProperty("class", "card")
        layout_cpu = QVBoxLayout(card_cpu)
        layout_cpu.setContentsMargins(14, 12, 14, 12)

        lbl_cpu_title = QLabel("Processador (CPU)")
        lbl_cpu_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout_cpu.addWidget(lbl_cpu_title)

        self.lbl_cpu_detail = QLabel("Uso: 0% | Núcleos lógicos: -")
        self.lbl_cpu_detail.setProperty("class", "secondary")
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
        layout_ram.setContentsMargins(14, 12, 14, 12)

        lbl_ram_title = QLabel("Memória RAM")
        lbl_ram_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout_ram.addWidget(lbl_ram_title)

        self.lbl_ram_detail = QLabel("Uso: 0.0 GB / 0.0 GB (0%)")
        self.lbl_ram_detail.setProperty("class", "secondary")
        layout_ram.addWidget(self.lbl_ram_detail)

        self.prog_ram = QProgressBar()
        self.prog_ram.setRange(0, 100)
        self.prog_ram.setValue(0)
        layout_ram.addWidget(self.prog_ram)

        row_metrics.addWidget(card_ram, stretch=1)
        layout.addLayout(row_metrics)

        # Cartão de Armazenamento / Discos
        card_disks = QFrame()
        card_disks.setProperty("class", "card")
        layout_disks = QVBoxLayout(card_disks)
        layout_disks.setContentsMargins(14, 12, 14, 12)
        layout_disks.setSpacing(10)

        lbl_disks_title = QLabel("Armazenamento e Unidades de Disco")
        lbl_disks_title.setStyleSheet("font-weight: 600; font-size: 13px;")
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
        self.table_disks.setFixedHeight(140)
        layout_disks.addWidget(self.table_disks)

        layout.addWidget(card_disks)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _update_metrics(self):
        try:
            m = get_realtime_metrics()
            # Atualiza CPU
            cpu_val = int(m["cpu_percent"])
            self.lbl_cpu_detail.setText(f"Uso: {cpu_val}% | Núcleos lógicos: {m['cpu_count']}")
            self.prog_cpu.setValue(cpu_val)

            # Atualiza RAM
            ram_val = int(m["mem_percent"])
            self.lbl_ram_detail.setText(
                f"Uso: {m['mem_used_gb']} GB de {m['mem_total_gb']} GB ({ram_val}%)"
            )
            self.prog_ram.setValue(ram_val)

            # Atualiza Discos
            disks = m["disks"]
            self.table_disks.setRowCount(len(disks))
            for row, d in enumerate(disks):
                self.table_disks.setItem(row, 0, QTableWidgetItem(f"{d['device']} ({d['mountpoint']})"))
                self.table_disks.setItem(row, 1, QTableWidgetItem(d["fstype"]))
                self.table_disks.setItem(row, 2, QTableWidgetItem(f"{d['total_gb']} GB"))
                self.table_disks.setItem(row, 3, QTableWidgetItem(f"{d['free_gb']} GB livre"))
                
                # Barra de uso na tabela
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(d["percent"]))
                bar.setFormat(f"{d['percent']}%")
                self.table_disks.setCellWidget(row, 4, bar)
        except Exception:
            pass

    def hideEvent(self, event):
        # Pausa o timer quando a tela não estiver visível para economizar CPU
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self.timer.start(2000)
        self._update_metrics()
        super().showEvent(event)
