"""
Interface gráfica de Controle de Privacidade e Debloat do Windows 10 e 11
(inspirada no projeto Raphire/Win11Debloat).
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.privacy.logic import (
    detect_windows_os_version,
    get_all_privacy_statuses,
    list_installed_bloatware_apps,
    remove_bloatware_packages,
    set_privacy_item,
)
from wintoolbox.tools.system.restore_points.logic import create_restore_point
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("system.privacy.ui")


@register
class PrivacyTool(Tool):
    id = "system.privacy"
    name = "Privacidade e Debloat do Windows"
    category = "Sistema"
    description = (
        "Desativação de telemetria, anúncios, Copilot, Recall AI, ajustes da barra de tarefas "
        "e remoção de bloatware nativo com validação automática para Windows 10 e Windows 11"
    )
    keywords = [
        "privacidade", "telemetria", "debloat", "copilot", "recall", "anuncios",
        "rastreamento", "windows 11", "windows 10", "win11debloat", "bloatware", "appx"
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PrivacyView(self, parent)


BLOAT_COLUMNS = [
    Column("name", "Aplicativo Pré-Instalado", width=240, tooltip=True),
    Column("status_label", "Status no Sistema", width=180),
    Column("pattern", "Identificador do Pacote (Appx)", width=240),
    Column("desc", "Descrição", stretch=True),
]


class PrivacyView(QWidget):
    def __init__(self, tool: PrivacyTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._os_info = detect_windows_os_version()
        self._checkbox_map: Dict[str, QCheckBox] = {}
        self._item_meta_map: Dict[str, Dict[str, Any]] = {}
        self._bloat_items: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        # Banner de Sistema Operacional Detectado
        os_card = QFrame()
        os_card.setProperty("class", "card")
        os_lay = QHBoxLayout(os_card)
        os_lay.setContentsMargins(14, 8, 14, 8)
        lbl_os = QLabel(f"<b>Sistema Detectado:</b> {self._os_info['label']}")
        os_lay.addWidget(lbl_os)
        os_lay.addStretch()

        os_lay.addWidget(QLabel("Filtro de Compatibilidade:"))
        self.cmb_os_filter = QComboBox()
        self.cmb_os_filter.addItem(f"Apenas opções para {self._os_info['label'].split('(')[0].strip()}", True)
        self.cmb_os_filter.addItem("Mostrar Todas as Opções (Windows 10 + Windows 11)", False)
        self.cmb_os_filter.currentIndexChanged.connect(self._load_statuses)
        os_lay.addWidget(self.cmb_os_filter)
        layout.addWidget(os_card)

        # Abas: 1. Ajustes de Privacidade/Interface, 2. Removedor de Bloatware (Appx)
        self._bloat_loaded = False
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tweaks_tab(), "Privacidade, Telemetria, IA e Interface")
        self.tabs.addTab(self._build_bloatware_tab(), "Removedor de Bloatware (Apps Pré-Instalados)")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, stretch=1)

        self._load_statuses()

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and not self._bloat_loaded:
            self._bloat_loaded = True
            self._scan_bloatware_async()

    def _build_tweaks_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        self.btn_select_all = QPushButton("Marcar Todas as Proteções")
        self.btn_select_all.clicked.connect(lambda: self._set_all_checks(True))
        bar.addWidget(self.btn_select_all)

        self.btn_unselect_all = QPushButton("Desmarcar Todos (Padrão Windows)")
        self.btn_unselect_all.clicked.connect(lambda: self._set_all_checks(False))
        bar.addWidget(self.btn_unselect_all)

        self.btn_reload = QPushButton("Recarregar do Registro")
        self.btn_reload.clicked.connect(self._load_statuses)
        bar.addWidget(self.btn_reload)

        bar.addStretch()
        layout.addLayout(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self.container_lay = QVBoxLayout(container)
        self.container_lay.setContentsMargins(0, 0, 4, 0)
        self.container_lay.setSpacing(10)

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        self.chk_create_restore = QCheckBox("Criar ponto de restauração do sistema antes de aplicar")
        self.chk_create_restore.setChecked(True)
        footer.addWidget(self.chk_create_restore)
        footer.addStretch()

        self.btn_apply = QPushButton("Aplicar Ajustes de Privacidade e Debloat")
        self.btn_apply.setProperty("accent", True)
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_apply.clicked.connect(self._apply_changes_async)
        footer.addWidget(self.btn_apply)

        layout.addLayout(footer)
        return tab

    def _build_bloatware_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.chk_bloat_all = QCheckBox("Marcar Visíveis")
        self.chk_bloat_all.toggled.connect(lambda c: self.table_bloat.set_all_visible_checked(c))
        top_bar.addWidget(self.chk_bloat_all)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_bloat_filter = QLineEdit()
        self.txt_bloat_filter.setClearButtonEnabled(True)
        self.txt_bloat_filter.setPlaceholderText("Buscar aplicativo nativo (ex: Xbox, Cortana, Bing, Clipchamp)...")
        self.txt_bloat_filter.textChanged.connect(self._apply_bloat_filter)
        top_bar.addWidget(self.txt_bloat_filter, stretch=1)

        self.cmb_bloat_state = QComboBox()
        self.cmb_bloat_state.addItems(["Apenas Instalados no Sistema", "Todo o Catálogo Win11Debloat"])
        self.cmb_bloat_state.currentIndexChanged.connect(self._apply_bloat_filter)
        top_bar.addWidget(self.cmb_bloat_state)

        self.btn_scan_bloat = QPushButton("Verificar Apps Instalados")
        self.btn_scan_bloat.clicked.connect(self._scan_bloatware_async)
        top_bar.addWidget(self.btn_scan_bloat)

        layout.addLayout(top_bar)

        self.table_bloat = DataTableView(BLOAT_COLUMNS, key="pattern", parent=tab, checkable=True)
        t = get_current_tokens()
        self.table_bloat.source_model.foreground = lambda rec, key: (
            (t.status_warning if rec.get("is_installed") else t.text_muted) if key == "status_label" else None
        )
        layout.addWidget(self.table_bloat, stretch=1)

        bottom_bar = QHBoxLayout()
        self.lbl_bloat_status = QLabel("Clique em 'Verificar Apps Instalados' ou selecione os apps na tabela.")
        self.lbl_bloat_status.setProperty("class", "secondary")
        bottom_bar.addWidget(self.lbl_bloat_status)
        bottom_bar.addStretch()

        self.btn_remove_bloat = QPushButton("Desinstalar Bloatware Marcado")
        self.btn_remove_bloat.setProperty("class", "danger")
        self.btn_remove_bloat.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px 16px;")
        self.btn_remove_bloat.clicked.connect(self._remove_bloatware_async)
        bottom_bar.addWidget(self.btn_remove_bloat)

        layout.addLayout(bottom_bar)
        return tab

    def _load_statuses(self) -> None:
        while self.container_lay.count() > 0:
            item = self.container_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkbox_map.clear()
        self._item_meta_map.clear()

        filter_os = bool(self.cmb_os_filter.currentData())
        statuses = get_all_privacy_statuses(filter_by_os=filter_os)

        # Agrupar por categoria
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for s in statuses:
            cat = s.get("category", "Geral")
            grouped.setdefault(cat, []).append(s)

        for cat_name, items in grouped.items():
            grp = QGroupBox(cat_name)
            grp_lay = QVBoxLayout(grp)
            grp_lay.setSpacing(8)

            for s in items:
                card = QFrame()
                card.setProperty("class", "card")
                card_lay = QHBoxLayout(card)
                card_lay.setContentsMargins(12, 8, 12, 8)
                card_lay.setSpacing(10)

                chk = QCheckBox()
                chk.setChecked(s["is_protected"])
                self._checkbox_map[s["id"]] = chk
                self._item_meta_map[s["id"]] = s
                card_lay.addWidget(chk)

                text_lay = QVBoxLayout()
                text_lay.setSpacing(2)
                adm_tag = " [Requer Admin]" if s.get("requires_admin") else ""
                lbl_name = QLabel(f"<b>{s['name']}</b>{adm_tag}")
                lbl_desc = QLabel(s["desc"])
                lbl_desc.setProperty("class", "secondary")
                lbl_desc.setWordWrap(True)
                text_lay.addWidget(lbl_name)
                text_lay.addWidget(lbl_desc)

                card_lay.addLayout(text_lay, stretch=1)
                grp_lay.addWidget(card)

            self.container_lay.addWidget(grp)

        self.container_lay.addStretch()

    def _set_all_checks(self, checked: bool) -> None:
        for chk in self._checkbox_map.values():
            chk.setChecked(checked)

    def _apply_changes_async(self) -> None:
        targets = {item_id: chk.isChecked() for item_id, chk in self._checkbox_map.items()}
        needs_admin = any(
            self._item_meta_map.get(item_id, {}).get("requires_admin")
            and chk.isChecked() != self._item_meta_map.get(item_id, {}).get("is_protected")
            for item_id, chk in self._checkbox_map.items()
        )
        if needs_admin and not is_admin():
            if prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason="Algumas políticas de telemetria e IA selecionadas gravam em HKLM e exigem privilégios de Administrador.",
            ):
                return

        self.btn_apply.setEnabled(False)
        needs_restore = self.chk_create_restore.isChecked()

        def _worker():
            messages = []
            if needs_restore:
                _ok, msg = create_restore_point("Antes de aplicar privacidade/debloat")
                messages.append(msg)

            for it_id, enabled in targets.items():
                _, m = set_privacy_item(it_id, enabled)
                messages.append(m)
            return messages

        def _on_done(_msgs):
            self.btn_apply.setEnabled(True)
            show_toast(self, "Ajustes de privacidade e debloat aplicados com sucesso!")
            self._load_statuses()

        def _on_error(err):
            self.btn_apply.setEnabled(True)
            show_toast(self, f"Erro ao aplicar ajustes: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _scan_bloatware_async(self) -> None:
        self.btn_scan_bloat.setEnabled(False)
        self.lbl_bloat_status.setText("Consultando pacotes Appx instalados no sistema...")

        def _on_done(items: List[Dict[str, Any]]):
            self.btn_scan_bloat.setEnabled(True)
            self._bloat_items = items
            self.table_bloat.set_records(items)
            self._apply_bloat_filter()

        def _on_err(err):
            self.btn_scan_bloat.setEnabled(True)
            self.lbl_bloat_status.setText(f"Erro ao verificar pacotes: {err}")

        TaskRunner.run(list_installed_bloatware_apps, on_success=_on_done, on_error=_on_err)

    def _apply_bloat_filter(self) -> None:
        only_installed = (self.cmb_bloat_state.currentIndex() == 0)
        self.table_bloat.proxy.set_predicate(
            (lambda r: bool(r.get("is_installed"))) if only_installed else None
        )
        self.table_bloat.proxy.set_text_filter(self.txt_bloat_filter.text())
        inst_count = sum(1 for r in self._bloat_items if r.get("is_installed"))
        self.lbl_bloat_status.setText(
            f"{inst_count} bloatware(s) identificado(s) no sistema de {len(self._bloat_items)} catalogados."
        )

    def _remove_bloatware_async(self) -> None:
        targets = self.table_bloat.target_records()
        patterns = [str(r["pattern"]) for r in targets if r.get("is_installed")]
        if not patterns:
            QMessageBox.information(
                self, "Aviso", "Marque pelo menos um aplicativo que esteja 'Instalado' para desinstalar."
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar Remoção de Bloatware",
            f"Deseja remover {len(patterns)} aplicativo(s) pré-instalado(s) selecionado(s)?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_remove_bloat.setEnabled(False)
        self.lbl_bloat_status.setText(f"Removendo {len(patterns)} pacote(s) Appx...")

        def _worker():
            return remove_bloatware_packages(patterns)

        def _on_done(res):
            self.btn_remove_bloat.setEnabled(True)
            ok, msg, _count = res
            self.table_bloat.clear_checked()
            self._scan_bloatware_async()
            if ok:
                QMessageBox.information(self, "Debloat Concluído", msg)
            else:
                QMessageBox.warning(self, "Aviso", msg)

        def _on_err(err):
            self.btn_remove_bloat.setEnabled(True)
            QMessageBox.critical(self, "Erro", str(err))

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_err)
