"""
Ferramenta: Planos de Energia do Windows.
Seleção de esquema ativo, desbloqueio do Desempenho Máximo e criação de novos planos personalizados.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.power_manager.logic import (
    BUILTIN_PLAN_GUIDS,
    create_custom_power_plan,
    delete_power_plan,
    get_battery_info,
    get_power_plans,
    set_active_power_plan,
    unlock_ultimate_performance_plan,
)
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class PowerManagerTool(Tool):
    id = "system.power_manager"
    name = "Planos de Energia"
    category = "Sistema"
    description = "Gerenciamento de esquemas de energia do Windows, criação de planos personalizados e Desempenho Máximo"
    keywords = ["energia", "power", "plano", "desempenho", "ultimate", "bateria", "powercfg"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PowerManagerView(self, parent)


class PowerManagerView(QWidget):
    def __init__(self, tool: PowerManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._plans = []
        self._build_ui()
        self._refresh_plans()
        self._refresh_battery()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(make_tool_header(self.tool))

        # 1. Esquema de Energia Ativo
        grp_plans = QGroupBox("Esquemas de Energia Disponíveis")
        plans_layout = QVBoxLayout(grp_plans)
        plans_layout.setSpacing(10)

        row_p = QHBoxLayout()
        row_p.addWidget(QLabel("Plano Selecionado:"))
        self.cmb_plans = QComboBox()
        self.cmb_plans.currentIndexChanged.connect(self._on_plan_selection_changed)
        row_p.addWidget(self.cmb_plans, 1)

        self.btn_apply_plan = QPushButton("Ativar Plano")
        self.btn_apply_plan.setProperty("class", "primary")
        self.btn_apply_plan.clicked.connect(self._on_apply_plan)
        row_p.addWidget(self.btn_apply_plan)

        self.btn_delete_plan = QPushButton("Excluir Plano")
        self.btn_delete_plan.clicked.connect(self._on_delete_plan)
        row_p.addWidget(self.btn_delete_plan)

        plans_layout.addLayout(row_p)

        row_extra = QHBoxLayout()
        self.lbl_battery = QLabel("Status da Bateria: Verificando...")
        self.lbl_battery.setProperty("class", "secondary")
        row_extra.addWidget(self.lbl_battery)
        row_extra.addStretch()

        self.btn_ultimate = QPushButton("Desbloquear Plano 'Desempenho Máximo'")
        self.btn_ultimate.setToolTip(
            "Libera o esquema oculto 'Ultimate Performance' da Microsoft via powercfg."
        )
        self.btn_ultimate.clicked.connect(self._on_unlock_ultimate)
        row_extra.addWidget(self.btn_ultimate)

        self.btn_refresh = QPushButton("Atualizar Lista")
        self.btn_refresh.clicked.connect(self._refresh_plans)
        row_extra.addWidget(self.btn_refresh)

        plans_layout.addLayout(row_extra)
        layout.addWidget(grp_plans)

        # 2. Criação de Novo Plano de Energia Personalizado
        grp_create = QGroupBox("Criar Novo Plano de Energia Personalizado")
        create_layout = QVBoxLayout(grp_create)
        create_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.txt_new_name = QLineEdit()
        self.txt_new_name.setPlaceholderText("Ex: Modo Jogos / Trabalho Noturno / Economia Extrema")
        form.addRow("Nome do Novo Plano:", self.txt_new_name)

        self.txt_new_desc = QLineEdit()
        self.txt_new_desc.setPlaceholderText("Descrição opcional do plano de energia...")
        form.addRow("Descrição:", self.txt_new_desc)

        self.cmb_base_plan = QComboBox()
        self.cmb_base_plan.addItem("Equilibrado (Recomendado)", "381b4222-f694-41f0-9685-ff5bb260df2e")
        self.cmb_base_plan.addItem("Alto Desempenho", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
        self.cmb_base_plan.addItem("Economia de Energia", "a1841308-3541-4fab-bc81-f71556f20b4a")
        form.addRow("Basear configurações em:", self.cmb_base_plan)

        create_layout.addLayout(form)

        # Grid de Tempos Limite (0 = Nunca)
        grid_timeouts = QGridLayout()
        grid_timeouts.setHorizontalSpacing(16)
        grid_timeouts.setVerticalSpacing(8)

        lbl_info_zero = QLabel("Tempos de inatividade (defina 0 minutos para 'Nunca desligar/suspender'):")
        lbl_info_zero.setProperty("class", "secondary")
        create_layout.addWidget(lbl_info_zero)

        grid_timeouts.addWidget(QLabel("Desligar vídeo (na Tomada):"), 0, 0)
        self.spin_mon_ac = QSpinBox()
        self.spin_mon_ac.setRange(0, 720)
        self.spin_mon_ac.setValue(15)
        self.spin_mon_ac.setSuffix(" min")
        grid_timeouts.addWidget(self.spin_mon_ac, 0, 1)

        grid_timeouts.addWidget(QLabel("Desligar vídeo (na Bateria):"), 0, 2)
        self.spin_mon_dc = QSpinBox()
        self.spin_mon_dc.setRange(0, 720)
        self.spin_mon_dc.setValue(5)
        self.spin_mon_dc.setSuffix(" min")
        grid_timeouts.addWidget(self.spin_mon_dc, 0, 3)

        grid_timeouts.addWidget(QLabel("Suspender PC (na Tomada):"), 1, 0)
        self.spin_sleep_ac = QSpinBox()
        self.spin_sleep_ac.setRange(0, 720)
        self.spin_sleep_ac.setValue(30)
        self.spin_sleep_ac.setSuffix(" min")
        grid_timeouts.addWidget(self.spin_sleep_ac, 1, 1)

        grid_timeouts.addWidget(QLabel("Suspender PC (na Bateria):"), 1, 2)
        self.spin_sleep_dc = QSpinBox()
        self.spin_sleep_dc.setRange(0, 720)
        self.spin_sleep_dc.setValue(15)
        self.spin_sleep_dc.setSuffix(" min")
        grid_timeouts.addWidget(self.spin_sleep_dc, 1, 3)

        create_layout.addLayout(grid_timeouts)

        self.chk_activate_new = QCheckBox("Tornar este novo plano ativo imediatamente após a criação")
        self.chk_activate_new.setChecked(True)
        create_layout.addWidget(self.chk_activate_new)

        btn_row = QHBoxLayout()
        self.btn_create = QPushButton("Criar Novo Plano de Energia")
        self.btn_create.setProperty("class", "primary")
        self.btn_create.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_create.clicked.connect(self._on_create_plan)
        btn_row.addWidget(self.btn_create)
        btn_row.addStretch()
        create_layout.addLayout(btn_row)

        layout.addWidget(grp_create)
        layout.addStretch()

    def _refresh_plans(self):
        self.cmb_plans.blockSignals(True)
        self.cmb_plans.clear()
        self._plans = get_power_plans()
        active_idx = 0
        for idx, p in enumerate(self._plans):
            suffix = " [Ativo]" if p["is_active"] else ""
            self.cmb_plans.addItem(f"{p['name']}{suffix}", p["guid"])
            if p["is_active"]:
                active_idx = idx

        if self._plans:
            self.cmb_plans.setCurrentIndex(active_idx)
        self.cmb_plans.blockSignals(False)
        self._on_plan_selection_changed()

    def _on_plan_selection_changed(self):
        guid = (self.cmb_plans.currentData() or "").lower()
        is_builtin = guid in BUILTIN_PLAN_GUIDS
        is_active = any(p["guid"].lower() == guid and p.get("is_active") for p in self._plans)
        self.btn_delete_plan.setEnabled(bool(guid and not is_builtin and not is_active))
        self.btn_apply_plan.setEnabled(bool(guid and not is_active))

    def _refresh_battery(self):
        b = get_battery_info()
        if b:
            plug = "Conectado à Tomada" if b["power_plugged"] else "Em Bateria"
            self.lbl_battery.setText(f"Bateria: {b['percent']}% ({plug}) — {b['time_left']}")
        else:
            self.lbl_battery.setText("Alimentação: Computador Desktop conectado à rede elétrica.")

    def _on_apply_plan(self):
        guid = self.cmb_plans.currentData()
        if not guid:
            return
        ok, msg = set_active_power_plan(guid)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_plans()
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _on_delete_plan(self):
        guid = self.cmb_plans.currentData()
        name = self.cmb_plans.currentText()
        if not guid:
            return
        confirm = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Deseja realmente excluir o plano de energia '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        ok, msg = delete_power_plan(guid)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_plans()
        else:
            QMessageBox.warning(self, "Aviso", msg)

    def _on_unlock_ultimate(self):
        ok, msg = unlock_ultimate_performance_plan()
        if ok:
            QMessageBox.information(self, "Desempenho Máximo", msg)
            self._refresh_plans()
        else:
            QMessageBox.warning(self, "Aviso", msg)

    def _on_create_plan(self):
        name = self.txt_new_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Aviso", "Digite um nome para o novo plano de energia.")
            return

        ok, msg, _guid = create_custom_power_plan(
            name=name,
            description=self.txt_new_desc.text().strip(),
            base_guid=self.cmb_base_plan.currentData(),
            monitor_ac_min=self.spin_mon_ac.value(),
            monitor_dc_min=self.spin_mon_dc.value(),
            standby_ac_min=self.spin_sleep_ac.value(),
            standby_dc_min=self.spin_sleep_dc.value(),
            activate=self.chk_activate_new.isChecked(),
        )
        if ok:
            self.txt_new_name.clear()
            self.txt_new_desc.clear()
            self._refresh_plans()
            QMessageBox.information(self, "Plano Criado", msg)
        else:
            QMessageBox.critical(self, "Erro", msg)
