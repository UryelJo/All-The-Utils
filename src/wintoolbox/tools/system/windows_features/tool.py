"""
Ferramenta: Recursos Opcionais do Windows.
Permite ativar e desativar componentes como Hyper-V, Sandbox, WSL e Telnet.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.windows_features.logic import (
    WindowsFeature,
    query_windows_features,
    set_windows_feature_state,
)


@register
class WindowsFeaturesTool(Tool):
    id = "system.windows_features"
    name = "Recursos do Windows"
    category = "Sistema"
    description = "Ative ou desative recursos opcionais do sistema operacional (Hyper-V, Sandbox, WSL, Telnet, SMB 1.0)"
    keywords = ["recursos", "features", "hyper-v", "sandbox", "wsl", "dism", "opcionais", "componentes", "telnet"]

    def __init__(self) -> None:
        super().__init__()
        self._all_features: List[WindowsFeature] = []

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior de Controles e Filtros
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar recurso por nome ou descrição...")
        self.txt_search.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_search, stretch=2)

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["Todos os Recursos", "Apenas Habilitados", "Apenas Desabilitados"])
        self.cmb_filter.currentTextChanged.connect(self._apply_filter)
        top_bar.addWidget(self.cmb_filter)

        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._load_features)
        top_bar.addWidget(self.btn_refresh)

        main_layout.addLayout(top_bar)

        # Tabela DataTableView
        columns = [
            Column("name", "Identificador Técnico", width=220),
            Column("display_name", "Nome de Exibição", width=240),
            Column("state_display", "Status", width=120),
            Column("description", "Descrição", stretch=True),
        ]
        self.table = DataTableView(columns, key="name", parent=container)
        main_layout.addWidget(self.table)

        # Barra de Ações Inferior
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.lbl_status = QLabel("Carregando recursos do sistema...")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        bottom_bar.addWidget(self.lbl_status)
        bottom_bar.addStretch()

        self.btn_enable = QPushButton("Ativar Recurso")
        self.btn_enable.clicked.connect(lambda: self._toggle_selected_feature(enable=True))
        bottom_bar.addWidget(self.btn_enable)

        self.btn_disable = QPushButton("Desativar Recurso")
        self.btn_disable.clicked.connect(lambda: self._toggle_selected_feature(enable=False))
        bottom_bar.addWidget(self.btn_disable)

        main_layout.addLayout(bottom_bar)

        self._load_features()
        return container

    def _load_features(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Consultando recursos opcionais via DISM/PowerShell...")

        TaskRunner.run(
            query_windows_features,
            on_success=self._on_load_success,
            on_error=self._on_load_error
        )

    def _on_load_success(self, features: List[WindowsFeature]) -> None:
        self._all_features = features
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"{len(features)} recursos encontrados no sistema.")
        self._apply_filter()

    def _on_load_error(self, err: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"Erro ao consultar recursos: {err}")

    def _apply_filter(self) -> None:
        query = self.txt_search.text().strip().lower()
        filter_mode = self.cmb_filter.currentText()

        records: List[Dict[str, Any]] = []
        for f in self._all_features:
            if filter_mode == "Apenas Habilitados" and not f.is_enabled:
                continue
            elif filter_mode == "Apenas Desabilitados" and f.is_enabled:
                continue

            if query:
                match_name = query in f.name.lower()
                match_display = query in f.display_name.lower()
                match_desc = query in f.description.lower()
                if not (match_name or match_display or match_desc):
                    continue

            records.append({
                "name": f.name,
                "display_name": f.display_name,
                "state_display": "Habilitado" if f.is_enabled else "Desabilitado",
                "description": f.description or "Sem descrição fornecida pelo sistema.",
            })

        self.table.set_records(records)

    def _toggle_selected_feature(self, enable: bool) -> None:
        rec = self.table.current_record()
        if not rec:
            QMessageBox.information(None, "Seleção necessária", "Selecione um recurso na tabela para alterar seu estado.")
            return

        feature_name = rec["name"]
        action_name = "ativar" if enable else "desativar"

        ans = QMessageBox.question(
            None,
            f"Confirmar {action_name}",
            f"Deseja realmente {action_name} o recurso '{feature_name}'?\n\nUma janela do Controle de Conta de Usuário (UAC) poderá solicitar permissão de administrador.",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans != QMessageBox.Yes:
            return

        self.lbl_status.setText(f"Alterando recurso '{feature_name}'...")

        def _worker() -> None:
            set_windows_feature_state(feature_name, enable)

        TaskRunner.run(
            _worker,
            on_success=lambda _: self._load_features(),
            on_error=lambda err: self.lbl_status.setText(f"Falha ao alterar: {err}")
        )
