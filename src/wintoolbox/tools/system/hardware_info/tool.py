"""
Ferramenta: Informações e Diagnóstico Detalhado de Hardware.
Apresenta inventário completo de CPU, GPU, pentes de RAM, Placa-mãe, BIOS e Bateria.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QVBoxLayout, QWidget, QMessageBox
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.hardware_info.logic import (
    HardwareInventory,
    query_hardware_inventory,
)


@register
class HardwareInfoTool(Tool):
    id = "system.hardware_info"
    name = "Informações de Hardware"
    category = "Sistema"
    description = "Inventário completo de CPU, GPU, pentes de memória RAM por slot, placa-mãe, BIOS e bateria"
    keywords = ["hardware", "cpu", "processador", "gpu", "placa de video", "ram", "memoria", "slot", "bios", "placa-mae", "bateria"]

    def __init__(self) -> None:
        super().__init__()
        self._inventory: Optional[HardwareInventory] = None

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior de Controles
        top_bar = QHBoxLayout()
        self.lbl_header = QLabel("Diagnóstico e Inventário de Hardware")
        self.lbl_header.setStyleSheet("font-size: 16px; font-weight: 600;")
        top_bar.addWidget(self.lbl_header)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("Atualizar Dados")
        self.btn_refresh.clicked.connect(self._load_hardware_info)
        top_bar.addWidget(self.btn_refresh)

        self.btn_export = QPushButton("Exportar Relatório...")
        self.btn_export.clicked.connect(self._export_report)
        top_bar.addWidget(self.btn_export)

        main_layout.addLayout(top_bar)

        # Abas de Categorias
        self.tabs = QTabWidget()

        # Aba 1: Visão Geral / CPU & Placa-Mãe
        self.tab_overview = QWidget()
        overview_layout = QVBoxLayout(self.tab_overview)
        overview_layout.setContentsMargins(12, 12, 12, 12)
        overview_layout.setSpacing(12)

        self.grp_cpu = QGroupBox("Processador (CPU)")
        self.grid_cpu = QGridLayout(self.grp_cpu)
        self.lbl_cpu_name = QLabel("Carregando...")
        self.lbl_cpu_cores = QLabel("-")
        self.lbl_cpu_clock = QLabel("-")
        self.lbl_cpu_arch = QLabel("-")
        self.grid_cpu.addWidget(QLabel("<b>Modelo:</b>"), 0, 0)
        self.grid_cpu.addWidget(self.lbl_cpu_name, 0, 1)
        self.grid_cpu.addWidget(QLabel("<b>Núcleos / Threads:</b>"), 0, 2)
        self.grid_cpu.addWidget(self.lbl_cpu_cores, 0, 3)
        self.grid_cpu.addWidget(QLabel("<b>Frequência Máxima:</b>"), 1, 0)
        self.grid_cpu.addWidget(self.lbl_cpu_clock, 1, 1)
        self.grid_cpu.addWidget(QLabel("<b>Arquitetura:</b>"), 1, 2)
        self.grid_cpu.addWidget(self.lbl_cpu_arch, 1, 3)
        overview_layout.addWidget(self.grp_cpu)

        self.grp_board = QGroupBox("Placa-Mãe e BIOS")
        self.grid_board = QGridLayout(self.grp_board)
        self.lbl_mb_model = QLabel("-")
        self.lbl_mb_manuf = QLabel("-")
        self.lbl_bios_ver = QLabel("-")
        self.lbl_bios_date = QLabel("-")
        self.grid_board.addWidget(QLabel("<b>Placa-Mãe:</b>"), 0, 0)
        self.grid_board.addWidget(self.lbl_mb_model, 0, 1)
        self.grid_board.addWidget(QLabel("<b>Fabricante:</b>"), 0, 2)
        self.grid_board.addWidget(self.lbl_mb_manuf, 0, 3)
        self.grid_board.addWidget(QLabel("<b>Versão da BIOS:</b>"), 1, 0)
        self.grid_board.addWidget(self.lbl_bios_ver, 1, 1)
        self.grid_board.addWidget(QLabel("<b>Data da BIOS:</b>"), 1, 2)
        self.grid_board.addWidget(self.lbl_bios_date, 1, 3)
        overview_layout.addWidget(self.grp_board)

        self.grp_bat = QGroupBox("Bateria do Sistema")
        self.grid_bat = QGridLayout(self.grp_bat)
        self.lbl_bat_status = QLabel("-")
        self.lbl_bat_health = QLabel("-")
        self.lbl_bat_cap = QLabel("-")
        self.grid_bat.addWidget(QLabel("<b>Status:</b>"), 0, 0)
        self.grid_bat.addWidget(self.lbl_bat_status, 0, 1)
        self.grid_bat.addWidget(QLabel("<b>Saúde / Desgaste:</b>"), 0, 2)
        self.grid_bat.addWidget(self.lbl_bat_health, 0, 3)
        self.grid_bat.addWidget(QLabel("<b>Capacidade Atual / Design:</b>"), 1, 0)
        self.grid_bat.addWidget(self.lbl_bat_cap, 1, 1, 1, 3)
        overview_layout.addWidget(self.grp_bat)
        overview_layout.addStretch()

        self.tabs.addTab(self.tab_overview, "Visão Geral")

        # Aba 2: Memória RAM por Slot
        self.tab_ram = QWidget()
        ram_layout = QVBoxLayout(self.tab_ram)
        ram_layout.setContentsMargins(12, 12, 12, 12)
        ram_layout.setSpacing(8)

        self.lbl_ram_summary = QLabel("Total Instalado: Calculando...")
        self.lbl_ram_summary.setStyleSheet("font-weight: 600; font-size: 13px;")
        ram_layout.addWidget(self.lbl_ram_summary)

        ram_cols = [
            Column("bank_label", "Slot / Banco", width=140),
            Column("capacity_gb", "Capacidade (GB)", width=130),
            Column("speed_mhz", "Velocidade (MHz)", width=130),
            Column("manufacturer", "Fabricante", width=140),
            Column("part_number", "Part Number", width=180),
        ]
        self.table_ram = DataTableView(ram_cols, key="bank_label", parent=self.tab_ram)
        ram_layout.addWidget(self.table_ram)
        self.tabs.addTab(self.tab_ram, "Memória RAM")

        # Aba 3: Adaptadores Gráficos (GPU)
        self.tab_gpu = QWidget()
        gpu_layout = QVBoxLayout(self.tab_gpu)
        gpu_layout.setContentsMargins(12, 12, 12, 12)
        gpu_layout.setSpacing(8)

        gpu_cols = [
            Column("name", "Placa de Vídeo", width=220),
            Column("vram_mb", "Memória VRAM (MB)", width=140),
            Column("driver_version", "Versão do Driver", width=160),
            Column("video_processor", "Processador de Vídeo", width=200),
        ]
        self.table_gpu = DataTableView(gpu_cols, key="name", parent=self.tab_gpu)
        gpu_layout.addWidget(self.table_gpu)
        self.tabs.addTab(self.tab_gpu, "Placas de Vídeo (GPU)")

        main_layout.addWidget(self.tabs)

        # Inicia carregamento dos dados
        self._load_hardware_info()
        return container

    def _load_hardware_info(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_header.setText("Consultando componentes de hardware via CIM/WMI...")

        TaskRunner.run(
            query_hardware_inventory,
            on_success=self._on_query_success,
            on_error=self._on_query_error
        )

    def _on_query_success(self, inv: HardwareInventory) -> None:
        self._inventory = inv
        self.btn_refresh.setEnabled(True)
        self.lbl_header.setText("Diagnóstico e Inventário de Hardware")

        # CPU
        self.lbl_cpu_name.setText(inv.cpu.name)
        self.lbl_cpu_cores.setText(f"{inv.cpu.cores} núcleos físicos / {inv.cpu.logical_processors} threads")
        self.lbl_cpu_clock.setText(f"{inv.cpu.max_clock_mhz} MHz")
        self.lbl_cpu_arch.setText(inv.cpu.architecture)

        # Placa-mãe e BIOS
        if inv.motherboard:
            self.lbl_mb_model.setText(inv.motherboard.product)
            self.lbl_mb_manuf.setText(inv.motherboard.manufacturer)
        if inv.bios:
            self.lbl_bios_ver.setText(inv.bios.version)
            self.lbl_bios_date.setText(inv.bios.release_date or "N/A")

        # Bateria
        if inv.battery and inv.battery.present:
            self.grp_bat.setVisible(True)
            self.lbl_bat_status.setText(f"{inv.battery.status} ({inv.battery.estimated_charge_percent}%)")
            health_txt = f"{inv.battery.health_percent}% de saúde" if inv.battery.health_percent else "N/A"
            cycles_txt = f" / {inv.battery.cycle_count} ciclos" if inv.battery.cycle_count else ""
            self.lbl_bat_health.setText(f"{health_txt}{cycles_txt}")

            d_cap = inv.battery.design_capacity_mwh or 0
            f_cap = inv.battery.full_charge_capacity_mwh or 0
            self.lbl_bat_cap.setText(f"{f_cap} mWh atuais / {d_cap} mWh projeto original")
        else:
            self.grp_bat.setVisible(False)

        # RAM
        self.lbl_ram_summary.setText(f"Total Instalado: {inv.total_ram_gb:.1f} GB em {len(inv.ram_slots)} pentes detectados")
        ram_rows = [
            {
                "bank_label": s.bank_label,
                "capacity_gb": f"{s.capacity_gb:.1f} GB",
                "speed_mhz": f"{s.speed_mhz} MHz" if s.speed_mhz else "N/A",
                "manufacturer": s.manufacturer,
                "part_number": s.part_number,
            }
            for s in inv.ram_slots
        ]
        self.table_ram.set_records(ram_rows)

        # GPU
        gpu_rows = [
            {
                "name": g.name,
                "vram_mb": f"{g.vram_mb} MB" if g.vram_mb > 0 else "Compartilhada",
                "driver_version": g.driver_version,
                "video_processor": g.video_processor,
            }
            for g in inv.gpus
        ]
        self.table_gpu.set_records(gpu_rows)

    def _on_query_error(self, err: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_header.setText(f"Falha ao ler hardware: {err}")

    def _export_report(self) -> None:
        if not self._inventory:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Relatório de Hardware",
            "relatorio_hardware.json",
            "Arquivo JSON (*.json);;Arquivo de Texto (*.txt)"
        )
        if file_path:
            p = Path(file_path)
            if p.suffix.lower() == ".json":
                p.write_text(json.dumps(self._inventory.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                txt = f"RELATÓRIO DE HARDWARE - ALL THE UTILS\n"
                txt += f"Processador: {self._inventory.cpu.name} ({self._inventory.cpu.cores}C/{self._inventory.cpu.logical_processors}T)\n"
                txt += f"Memória Total: {self._inventory.total_ram_gb:.1f} GB\n"
                p.write_text(txt, encoding="utf-8")
