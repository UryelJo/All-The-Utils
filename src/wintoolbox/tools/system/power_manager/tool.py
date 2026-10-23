"""
Ferramenta: Planos de Energia e Desligamento Agendado.
Interface para seleção de esquema de energia, status de bateria e agendador de ações do sistema.
"""
from typing import Optional
from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QRadioButton, QSpinBox, QTimeEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.power_manager.logic import (
    cancel_scheduled_shutdown, get_battery_info, get_power_plans,
    schedule_system_action, set_active_power_plan
)


@register
class PowerManagerTool(Tool):
    id = "system.power_manager"
    name = "Planos de Energia e Desligamento"
    category = "Sistema"
    description = "Gerenciamento de esquemas de energia do Windows, monitor de bateria e agendador de desligamento/reinício"
    keywords = ["energia", "power", "desligar", "reiniciar", "suspender", "bateria", "shutdown", "timer"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PowerManagerView(self, parent)


class PowerManagerView(QWidget):
    def __init__(self, tool: PowerManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()
        self._refresh_plans()
        self._refresh_battery()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # 1. Esquema de Energia
        grp_plans = QGroupBox("Planos de Energia do Windows")
        plans_layout = QVBoxLayout(grp_plans)

        row_p = QHBoxLayout()
        row_p.addWidget(QLabel("Plano Atual:"))
        self.cmb_plans = QComboBox()
        row_p.addWidget(self.cmb_plans, 1)

        self.btn_apply_plan = QPushButton("Aplicar Plano")
        self.btn_apply_plan.setProperty("class", "primary")
        self.btn_apply_plan.clicked.connect(self._on_apply_plan)
        row_p.addWidget(self.btn_apply_plan)
        plans_layout.addLayout(row_p)

        self.lbl_battery = QLabel("Status da Bateria: Verificando...")
        self.lbl_battery.setStyleSheet("color: #888890; font-size: 11px;")
        plans_layout.addWidget(self.lbl_battery)

        layout.addWidget(grp_plans)

        # 2. Agendador de Ações
        grp_timer = QGroupBox("Agendar Ação do Sistema")
        timer_layout = QVBoxLayout(grp_timer)
        timer_layout.setSpacing(10)

        # Ação
        row_act = QHBoxLayout()
        row_act.addWidget(QLabel("Ação:"))
        self.cmb_action = QComboBox()
        self.cmb_action.addItem("Desligar o Computador", "shutdown")
        self.cmb_action.addItem("Reiniciar o Computador", "restart")
        self.cmb_action.addItem("Suspender (Sleep)", "sleep")
        self.cmb_action.addItem("Bloquear Estação de Trabalho", "lock")
        row_act.addWidget(self.cmb_action, 1)
        timer_layout.addLayout(row_act)

        # Modo de Agendamento: Temporizador em minutos vs Horário
        self.rb_timer = QRadioButton("Executar daqui a:")
        self.rb_timer.setChecked(True)
        self.rb_time = QRadioButton("Executar no horário exato:")

        row_spin = QHBoxLayout()
        row_spin.addWidget(self.rb_timer)
        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(1, 1440)
        self.spin_minutes.setValue(30)
        self.spin_minutes.setSuffix(" minutos")
        row_spin.addWidget(self.spin_minutes)
        row_spin.addStretch()
        timer_layout.addLayout(row_spin)

        row_clock = QHBoxLayout()
        row_clock.addWidget(self.rb_time)
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime.currentTime().addSecs(3600))
        row_clock.addWidget(self.time_edit)
        row_clock.addStretch()
        timer_layout.addLayout(row_clock)

        # Botões de Ação
        btn_row = QHBoxLayout()
        self.btn_schedule = QPushButton("Agendar Ação Agora")
        self.btn_schedule.setProperty("class", "primary")
        self.btn_schedule.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_schedule.clicked.connect(self._on_schedule_action)
        btn_row.addWidget(self.btn_schedule)

        self.btn_cancel = QPushButton("Cancelar Agendamento Ativo")
        self.btn_cancel.clicked.connect(self._on_cancel_action)
        btn_row.addWidget(self.btn_cancel)

        btn_row.addStretch()
        timer_layout.addLayout(btn_row)

        layout.addWidget(grp_timer)
        layout.addStretch()

    def _refresh_plans(self):
        self.cmb_plans.clear()
        plans = get_power_plans()
        active_idx = 0
        for idx, p in enumerate(plans):
            suffix = " (Ativo)" if p["is_active"] else ""
            self.cmb_plans.addItem(f"{p['name']}{suffix}", p["guid"])
            if p["is_active"]:
                active_idx = idx

        if plans:
            self.cmb_plans.setCurrentIndex(active_idx)

    def _refresh_battery(self):
        b = get_battery_info()
        if b:
            plug = "Conectado à Tomada" if b["power_plugged"] else "Em Bateria"
            self.lbl_battery.setText(f"Bateria: {b['percent']}% ({plug}) — {b['time_left']}")
        else:
            self.lbl_battery.setText("Bateria: Computador Desktop conectado à rede elétrica.")

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

    def _on_schedule_action(self):
        action = self.cmb_action.currentData()

        if self.rb_timer.isChecked():
            delay_sec = self.spin_minutes.value() * 60
        else:
            now = QTime.currentTime()
            target = self.time_edit.time()
            sec_diff = now.secsTo(target)
            if sec_diff <= 0:
                # Dia seguinte
                sec_diff += 86400
            delay_sec = sec_diff

        ok, msg = schedule_system_action(action, delay_sec)
        if ok:
            QMessageBox.information(self, "Agendamento do Sistema", msg)
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _on_cancel_action(self):
        ok, msg = cancel_scheduled_shutdown()
        if ok:
            QMessageBox.information(self, "Cancelado", msg)
        else:
            QMessageBox.warning(self, "Aviso", msg)
