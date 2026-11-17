"""
Ferramenta: Recursos Opcionais do Windows.
Permite ativar e desativar componentes como Hyper-V, Sandbox, WSL e Telnet.
"""
import subprocess
from typing import Any, Dict, List
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import (
    bind_admin_prompt_on_show,
    is_admin,
    prompt_elevation_dialog,
    request_elevation,
)
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.windows_features.logic import (
    WindowsFeature,
    query_windows_features,
    set_windows_feature_state,
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class WindowsFeaturesTool(Tool):
    id = "system.windows_features"
    name = "Recursos do Windows"
    category = "Sistema"
    description = "Ative ou desative recursos opcionais do sistema operacional (Hyper-V, Sandbox, WSL, .NET 3.5, Telnet)"
    keywords = ["recursos", "features", "hyper-v", "sandbox", "wsl", "dism", "opcionais", "componentes", "telnet"]

    def __init__(self) -> None:
        super().__init__()
        self._all_features: List[WindowsFeature] = []

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(10)
        main_layout.addWidget(make_tool_header(self))

        # Banner de aviso quando não está como Administrador
        if not is_admin():
            admin_card = QFrame()
            admin_card.setProperty("class", "card")
            adm_lay = QHBoxLayout(admin_card)
            adm_lay.setContentsMargins(14, 10, 14, 10)
            lbl_warn = QLabel(
                "<b>Atenção:</b> O DISM do Windows exige privilégios de <b>Administrador</b> para listar e "
                "alterar os Recursos Opcionais do Sistema (Hyper-V, Sandbox, WSL)."
            )
            lbl_warn.setWordWrap(True)
            adm_lay.addWidget(lbl_warn, stretch=1)

            btn_elev = QPushButton("Executar como Administrador")
            btn_elev.setProperty("class", "primary")
            btn_elev.clicked.connect(lambda: request_elevation())
            adm_lay.addWidget(btn_elev)
            main_layout.addWidget(admin_card)

        # Barra Superior de Controles e Filtros
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Buscar recurso por nome ou descrição (ex: Hyper-V, Sandbox, WSL, NetFx3)...")
        self.txt_search.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_search, stretch=2)

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["Todos os Recursos", "Apenas Habilitados", "Apenas Desabilitados"])
        self.cmb_filter.currentTextChanged.connect(self._apply_filter)
        top_bar.addWidget(self.cmb_filter)

        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._load_features)
        top_bar.addWidget(self.btn_refresh)

        btn_native = QPushButton("Abrir Janela Clássica (optionalfeatures)")
        btn_native.clicked.connect(lambda: subprocess.Popen(["optionalfeatures.exe"]))
        top_bar.addWidget(btn_native)

        main_layout.addLayout(top_bar)

        # Tabela DataTableView
        columns = [
            Column("name", "Identificador Técnico", width=230),
            Column("display_name", "Nome de Exibição", width=250),
            Column("state_display", "Status", width=130),
            Column("description", "Descrição", stretch=True),
        ]
        self.table = DataTableView(columns, key="name", parent=container)
        t = get_current_tokens()
        self.table.source_model.foreground = lambda rec, key: (
            (t.status_success if rec.get("state_display") == "Habilitado" else t.text_muted)
            if key == "state_display"
            else None
        )
        main_layout.addWidget(self.table, stretch=1)

        # Barra de Ações Inferior
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.lbl_status = QLabel("Pronto.")
        self.lbl_status.setProperty("class", "secondary")
        bottom_bar.addWidget(self.lbl_status)
        bottom_bar.addStretch()

        self.btn_enable = QPushButton("Ativar Recurso Selecionado")
        self.btn_enable.setProperty("class", "primary")
        self.btn_enable.clicked.connect(lambda: self._toggle_selected_feature(enable=True))
        bottom_bar.addWidget(self.btn_enable)

        self.btn_disable = QPushButton("Desativar Recurso Selecionado")
        self.btn_disable.clicked.connect(lambda: self._toggle_selected_feature(enable=False))
        bottom_bar.addWidget(self.btn_disable)

        main_layout.addLayout(bottom_bar)

        # Solicita Administrador automaticamente ao abrir a tela caso não esteja elevado
        bind_admin_prompt_on_show(
            container,
            tool_name=self.name,
            reason="O comando DISM / Get-WindowsOptionalFeature exige execução como Administrador para listar os recursos do sistema.",
        )

        self._load_features()
        return container

    def _load_features(self) -> None:
        if not is_admin():
            self.lbl_status.setText(
                "Permissão de Administrador necessária para consultar recursos opcionais via DISM."
            )
            return

        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Consultando recursos opcionais via DISM/PowerShell...")

        TaskRunner.run(
            query_windows_features,
            on_success=self._on_load_success,
            on_error=self._on_load_error,
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
                "description": f.description or "Componente opcional do sistema operacional Windows.",
            })

        self.table.set_records(records)

    def _toggle_selected_feature(self, enable: bool) -> None:
        if not is_admin():
            prompt_elevation_dialog(
                None,
                tool_name=self.name,
                reason="Ativar ou desativar recursos opcionais do Windows requer privilégios de Administrador.",
            )
            return

        rec = self.table.current_record()
        if not rec:
            QMessageBox.information(None, "Seleção necessária", "Selecione um recurso na tabela para alterar seu estado.")
            return

        feature_name = rec["name"]
        action_name = "ativar" if enable else "desativar"

        ans = QMessageBox.question(
            None,
            f"Confirmar {action_name}",
            f"Deseja realmente {action_name} o recurso '{feature_name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return

        self.lbl_status.setText(f"Alterando recurso '{feature_name}'...")

        def _worker() -> None:
            set_windows_feature_state(feature_name, enable)

        TaskRunner.run(
            _worker,
            on_success=lambda _: self._load_features(),
            on_error=lambda err: self.lbl_status.setText(f"Falha ao alterar: {err}"),
        )
