"""
Ferramenta: Diagnóstico de Dispositivos e Histórico USB.
Identifica problemas de hardware (Código 43, 10, 28) e periféricos USB conectados.
"""
from typing import Any, Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.devices.logic import (
    PnpDevice,
    query_pnp_devices,
    query_usb_storage_history,
)


@register
class DevicesManagerTool(Tool):
    id = "system.devices"
    name = "Diagnóstico de Dispositivos (PnP e USB)"
    category = "Sistema"
    description = "Identifique dispositivos com erros de driver (Código 43, 10) e histórico de periféricos USB"
    keywords = ["dispositivos", "pnp", "usb", "drivers", "hardware", "codigo 43", "codigo 10", "gerenciador", "perifericos"]

    def __init__(self) -> None:
        super().__init__()
        self._all_pnp: List[PnpDevice] = []

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel("Diagnóstico de Hardware e Periféricos")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("Atualizar Diagnóstico")
        self.btn_refresh.clicked.connect(self._load_all_data)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Abas
        self.tabs = QTabWidget()

        # Aba 1: Dispositivos com Problemas
        tab_errors = QWidget()
        err_layout = QVBoxLayout(tab_errors)
        err_layout.setContentsMargins(8, 8, 8, 8)
        self.lbl_err_count = QLabel("Verificando se há falhas de driver ou conflitos de hardware...")
        err_layout.addWidget(self.lbl_err_count)

        err_cols = [
            Column("name", "Nome do Dispositivo", width=240),
            Column("error_description", "Diagnóstico / Código de Erro", width=280),
            Column("class_name", "Classe", width=140),
            Column("manufacturer", "Fabricante", width=160),
            Column("device_id", "ID do Hardware", stretch=True),
        ]
        self.table_errors = DataTableView(err_cols, key="device_id", parent=tab_errors)
        err_layout.addWidget(self.table_errors)
        self.tabs.addTab(tab_errors, "Dispositivos com Falhas")

        # Aba 2: Todos os Dispositivos PnP
        tab_all = QWidget()
        all_layout = QVBoxLayout(tab_all)
        all_layout.setContentsMargins(8, 8, 8, 8)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar dispositivo por nome, classe ou fabricante...")
        self.txt_search.textChanged.connect(self._apply_pnp_filter)
        all_layout.addWidget(self.txt_search)

        all_cols = [
            Column("name", "Nome do Dispositivo", width=260),
            Column("class_name", "Classe", width=160),
            Column("status", "Status", width=100),
            Column("manufacturer", "Fabricante", width=180),
            Column("device_id", "ID do Hardware", stretch=True),
        ]
        self.table_all = DataTableView(all_cols, key="device_id", parent=tab_all)
        all_layout.addWidget(self.table_all)
        self.tabs.addTab(tab_all, "Todos os Dispositivos")

        # Aba 3: Histórico USB
        tab_usb = QWidget()
        usb_layout = QVBoxLayout(tab_usb)
        usb_layout.setContentsMargins(8, 8, 8, 8)

        usb_cols = [
            Column("FriendlyName", "Nome do Periférico", width=280),
            Column("DeviceName", "Identificador Técnico", width=240),
            Column("SerialNumber", "Número de Série", stretch=True),
        ]
        self.table_usb = DataTableView(usb_cols, key="SerialNumber", parent=tab_usb)
        usb_layout.addWidget(self.table_usb)
        self.tabs.addTab(tab_usb, "Histórico USB (Armazenamento)")

        main_layout.addWidget(self.tabs)

        self._load_all_data()
        return container

    def _load_all_data(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_title.setText("Consultando dispositivos e periféricos do Windows...")

        def _worker() -> Dict[str, Any]:
            pnp = query_pnp_devices(errors_only=False)
            usb = query_usb_storage_history()
            return {"pnp": pnp, "usb": usb}

        TaskRunner.run(
            _worker,
            on_success=self._on_load_success,
            on_error=self._on_load_error
        )

    def _on_load_success(self, data: Dict[str, Any]) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_title.setText("Diagnóstico de Hardware e Periféricos")

        pnp_list: List[PnpDevice] = data.get("pnp", [])
        self._all_pnp = pnp_list

        # Dispositivos com erro
        error_devices = [d for d in pnp_list if d.has_error]
        if error_devices:
            self.lbl_err_count.setText(f"{len(error_devices)} dispositivo(s) com erro ou problemas encontrados:")
            self.lbl_err_count.setStyleSheet("color: #dc2626; font-weight: 600;")
        else:
            self.lbl_err_count.setText("Nenhum erro de hardware ou conflito de driver detectado no momento.")
            self.lbl_err_count.setStyleSheet("color: #16a34a; font-weight: 600;")

        self.table_errors.set_records([d.to_dict() for d in error_devices])
        self._apply_pnp_filter()

        # USB
        usb_list = data.get("usb", [])
        self.table_usb.set_records(usb_list)

    def _on_load_error(self, err: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_title.setText(f"Erro ao consultar dispositivos: {err}")

    def _apply_pnp_filter(self) -> None:
        q = self.txt_search.text().strip().lower()
        records: List[Dict[str, Any]] = []

        for d in self._all_pnp:
            if q:
                match_name = q in d.name.lower()
                match_class = q in d.class_name.lower()
                match_manuf = q in d.manufacturer.lower()
                if not (match_name or match_class or match_manuf):
                    continue

            records.append(d.to_dict())

        self.table_all.set_records(records)
