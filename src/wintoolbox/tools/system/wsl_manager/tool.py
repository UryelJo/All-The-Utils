"""
Ferramenta: Gerenciador do Subsistema do Windows para Linux (WSL).
Controle distribuições, encerramento de VMs, exportação e configuração de hardware via .wslconfig.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.wsl_manager.logic import (
    WslDistro,
    export_distro_tar,
    parse_wslconfig,
    query_installed_distros,
    set_default_distro,
    shutdown_all_wsl,
    stop_distro,
    write_wslconfig,
)


@register
class WslManagerTool(Tool):
    id = "system.wsl_manager"
    name = "Gerenciador do WSL (Linux)"
    category = "Sistema"
    description = "Controle distribuições WSL, exporte backups tar e configure limites de RAM/CPU via .wslconfig"
    keywords = ["wsl", "linux", "ubuntu", "debian", "docker", "distros", "wsl2", "wslconfig", "backup"]

    def __init__(self) -> None:
        super().__init__()
        self._distros: List[WslDistro] = []

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("Gerenciamento do Subsistema Windows para Linux (WSL)")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._load_distros)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        self.tabs = QTabWidget()

        # Aba 1: Distribuições
        tab_distros = QWidget()
        distro_layout = QVBoxLayout(tab_distros)
        distro_layout.setContentsMargins(8, 8, 8, 8)
        distro_layout.setSpacing(10)

        # Ações de Distro
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(8)

        self.btn_stop = QPushButton("Parar Distro")
        self.btn_stop.clicked.connect(self._stop_selected)
        actions_bar.addWidget(self.btn_stop)

        self.btn_default = QPushButton("Definir como Padrão")
        self.btn_default.clicked.connect(self._set_default_selected)
        actions_bar.addWidget(self.btn_default)

        self.btn_export = QPushButton("Exportar Backup (.tar)...")
        self.btn_export.clicked.connect(self._export_selected)
        actions_bar.addWidget(self.btn_export)

        self.btn_shutdown = QPushButton("Encerrar Todo o WSL")
        self.btn_shutdown.setStyleSheet("color: #dc2626;")
        self.btn_shutdown.clicked.connect(self._shutdown_wsl)
        actions_bar.addWidget(self.btn_shutdown)

        actions_bar.addStretch()
        distro_layout.addLayout(actions_bar)

        # Tabela DataTableView
        columns = [
            Column("name", "Nome da Distribuição", width=220),
            Column("state", "Estado", width=140),
            Column("version_display", "Versão", width=120),
            Column("default_display", "Distribuição Padrão", width=160),
        ]
        self.table = DataTableView(columns, key="name", parent=tab_distros)
        distro_layout.addWidget(self.table)
        self.tabs.addTab(tab_distros, "Distribuições Instaladas")

        # Aba 2: Recursos Globais (.wslconfig)
        tab_config = QWidget()
        cfg_layout = QVBoxLayout(tab_config)
        cfg_layout.setContentsMargins(16, 16, 16, 16)
        cfg_layout.setSpacing(14)

        lbl_cfg_desc = QLabel("Configure limites de memória RAM, CPU e swap alocados para o WSL2.")
        lbl_cfg_desc.setStyleSheet("color: #64748b; font-size: 13px;")
        cfg_layout.addWidget(lbl_cfg_desc)

        grid_cfg = QGridLayout()
        grid_cfg.setHorizontalSpacing(16)
        grid_cfg.setVerticalSpacing(12)

        grid_cfg.addWidget(QLabel("Limite de Memória RAM:"), 0, 0)
        self.txt_ram = QLineEdit()
        self.txt_ram.setPlaceholderText("Ex: 8GB ou 4GB")
        grid_cfg.addWidget(self.txt_ram, 0, 1)

        grid_cfg.addWidget(QLabel("Núcleos de Processamento (CPU):"), 1, 0)
        self.spin_cpu = QSpinBox()
        self.spin_cpu.setRange(0, 64)
        self.spin_cpu.setValue(0)
        self.spin_cpu.setSpecialValueText("Padrão do Sistema")
        grid_cfg.addWidget(self.spin_cpu, 1, 1)

        grid_cfg.addWidget(QLabel("Tamanho do Arquivo Swap:"), 2, 0)
        self.txt_swap = QLineEdit()
        self.txt_swap.setPlaceholderText("Ex: 2GB ou 0 (desabilitar swap)")
        grid_cfg.addWidget(self.txt_swap, 2, 1)

        cfg_layout.addLayout(grid_cfg)

        self.btn_save_config = QPushButton("Salvar e Aplicar (.wslconfig)")
        self.btn_save_config.setStyleSheet("font-weight: 600;")
        self.btn_save_config.clicked.connect(self._save_config)
        cfg_layout.addWidget(self.btn_save_config)
        cfg_layout.addStretch()

        self.tabs.addTab(tab_config, "Configuração de Recursos (.wslconfig)")
        main_layout.addWidget(self.tabs)

        # Status
        self.lbl_status = QLabel("Carregando distribuições...")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_status)

        self._load_distros()
        self._load_config()
        return container

    def _load_distros(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Consultando distribuições WSL instaladas...")

        TaskRunner.run(
            query_installed_distros,
            on_success=self._on_distros_loaded,
            on_error=self._on_distros_error
        )

    def _on_distros_loaded(self, distros: List[WslDistro]) -> None:
        self._distros = distros
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"{len(distros)} distribuição(ões) WSL detectada(s).")

        rows = [
            {
                "name": d.name,
                "state": "Em Execução" if "running" in d.state.lower() else "Parada",
                "version_display": f"WSL {d.version}",
                "default_display": "Sim (Padrão)" if d.is_default else "Não",
            }
            for d in distros
        ]
        self.table.set_records(rows)

    def _on_distros_error(self, err: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"Erro ao listar WSL: {err}")

    def _load_config(self) -> None:
        cfg = parse_wslconfig()
        if "memory" in cfg:
            self.txt_ram.setText(cfg["memory"])
        if "processors" in cfg and cfg["processors"].isdigit():
            self.spin_cpu.setValue(int(cfg["processors"]))
        if "swap" in cfg:
            self.txt_swap.setText(cfg["swap"])

    def _save_config(self) -> None:
        mem = self.txt_ram.text().strip() or None
        cpu = self.spin_cpu.value() if self.spin_cpu.value() > 0 else None
        swap = self.txt_swap.text().strip() or None

        p = write_wslconfig(memory=mem, processors=cpu, swap=swap)
        QMessageBox.information(
            None,
            "Configuração Salva",
            f"Arquivo .wslconfig atualizado com sucesso em:\n{p}\n\nPara aplicar as novas configurações de hardware, encerre o WSL pelo botão 'Encerrar Todo o WSL'."
        )

    def _stop_selected(self) -> None:
        rec = self.table.current_record()
        if not rec:
            return
        name = rec["name"]
        self.lbl_status.setText(f"Parando '{name}'...")

        def _worker() -> None:
            stop_distro(name)

        TaskRunner.run(_worker, on_success=lambda _: self._load_distros())

    def _set_default_selected(self) -> None:
        rec = self.table.current_record()
        if not rec:
            return
        name = rec["name"]
        set_default_distro(name)
        self._load_distros()

    def _shutdown_wsl(self) -> None:
        ans = QMessageBox.question(
            None,
            "Encerrar WSL",
            "Deseja realmente encerrar todas as distribuições e desligar o subsistema WSL2?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            shutdown_all_wsl()
            self._load_distros()

    def _export_selected(self) -> None:
        rec = self.table.current_record()
        if not rec:
            return
        name = rec["name"]

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            f"Exportar Backup da Distro {name}",
            f"{name}_backup.tar",
            "Arquivo TAR (*.tar)"
        )
        if file_path:
            self.lbl_status.setText(f"Exportando '{name}' para {Path(file_path).name}... Isso pode levar alguns minutos.")
            dest = Path(file_path)

            def _worker() -> None:
                export_distro_tar(name, dest)

            TaskRunner.run(
                _worker,
                on_success=lambda _: self.lbl_status.setText(f"Backup de '{name}' concluído com sucesso!"),
                on_error=lambda err: self.lbl_status.setText(f"Erro ao exportar backup: {err}")
            )
