"""
Ferramenta: Manter o Sistema Acordado (Keep Awake).
Impede que o Windows suspenda ou desligue a tela durante tarefas longas.
"""
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.keep_awake.logic import (
    apply_keep_awake,
    format_remaining_seconds,
    release_keep_awake,
)


@register
class KeepAwakeTool(Tool):
    id = "system.keep_awake"
    name = "Manter Sistema Acordado"
    category = "Sistema"
    description = "Impede suspensão automática e desligamento de tela durante apresentações, downloads e tarefas longas"
    keywords = ["awake", "keep awake", "caffeine", "suspensao", "tela", "energia", "hibernacao", "sleep", "monitor"]

    def __init__(self) -> None:
        super().__init__()
        self._is_active: bool = False
        self._target_end_time: Optional[float] = None
        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_tick)

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Card de Status Principal
        self.status_card = QFrame()
        self.status_card.setStyleSheet(
            "background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px;"
        )
        card_layout = QVBoxLayout(self.status_card)
        card_layout.setSpacing(10)

        self.lbl_status_title = QLabel("Status: Inativo")
        self.lbl_status_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #475569;")
        card_layout.addWidget(self.lbl_status_title)

        self.lbl_status_desc = QLabel("O sistema segue as regras normais de economia de energia e suspensão do Windows.")
        self.lbl_status_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        card_layout.addWidget(self.lbl_status_desc)

        self.lbl_timer_countdown = QLabel("")
        self.lbl_timer_countdown.setStyleSheet("font-size: 20px; font-weight: 700; color: #0284c7;")
        self.lbl_timer_countdown.setVisible(False)
        card_layout.addWidget(self.lbl_timer_countdown)

        # Botão Principal de Alternância
        self.btn_toggle = QPushButton("Ativar Modo Acordado")
        self.btn_toggle.setFixedHeight(42)
        self.btn_toggle.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.btn_toggle.clicked.connect(self._toggle_active)
        card_layout.addWidget(self.btn_toggle)

        main_layout.addWidget(self.status_card)

        # Painel de Modo de Operação
        grp_mode = QGroupBox("Duração da Ativação")
        mode_layout = QVBoxLayout(grp_mode)
        mode_layout.setSpacing(10)

        self.rb_indefinite = QRadioButton("Manter acordado indefinidamente (até desativação manual)")
        self.rb_indefinite.setChecked(True)
        self.rb_indefinite.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.rb_indefinite)

        self.rb_timed = QRadioButton("Ativar por tempo determinado:")
        self.rb_timed.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.rb_timed)

        # Controles de Tempo
        time_box = QHBoxLayout()
        time_box.setContentsMargins(20, 0, 0, 0)
        self.cmb_presets = QComboBox()
        self.cmb_presets.addItems([
            "30 minutos",
            "1 hora",
            "2 horas",
            "4 horas",
            "8 horas",
            "Personalizado"
        ])
        self.cmb_presets.setEnabled(False)
        self.cmb_presets.currentTextChanged.connect(self._on_preset_changed)
        time_box.addWidget(self.cmb_presets)

        self.lbl_custom_min = QLabel("Minutos:")
        self.lbl_custom_min.setEnabled(False)
        time_box.addWidget(self.lbl_custom_min)

        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(1, 1440)
        self.spin_minutes.setValue(45)
        self.spin_minutes.setEnabled(False)
        time_box.addWidget(self.spin_minutes)
        time_box.addStretch()

        mode_layout.addLayout(time_box)
        main_layout.addWidget(grp_mode)

        # Opções de Alvo
        grp_targets = QGroupBox("Componentes Protegidos")
        targets_layout = QVBoxLayout(grp_targets)

        self.chk_keep_display = QCheckBox("Manter a tela ligada (impede desligamento do monitor)")
        self.chk_keep_display.setChecked(True)
        targets_layout.addWidget(self.chk_keep_display)

        self.chk_keep_system = QCheckBox("Manter sistema acordado (impede suspensão/sleep e hibernação)")
        self.chk_keep_system.setChecked(True)
        targets_layout.addWidget(self.chk_keep_system)

        main_layout.addWidget(grp_targets)
        main_layout.addStretch()

        return container

    def _on_mode_changed(self) -> None:
        is_timed = self.rb_timed.isChecked()
        self.cmb_presets.setEnabled(is_timed)
        is_custom = is_timed and (self.cmb_presets.currentText() == "Personalizado")
        self.lbl_custom_min.setEnabled(is_custom)
        self.spin_minutes.setEnabled(is_custom)

    def _on_preset_changed(self, text: str) -> None:
        is_custom = (text == "Personalizado")
        self.lbl_custom_min.setEnabled(is_custom)
        self.spin_minutes.setEnabled(is_custom)

    def _toggle_active(self) -> None:
        if self._is_active:
            self._deactivate()
        else:
            self._activate()

    def _activate(self) -> None:
        keep_disp = self.chk_keep_display.isChecked()
        keep_sys = self.chk_keep_system.isChecked()

        success = apply_keep_awake(keep_display=keep_disp, keep_system=keep_sys)
        if not success:
            return

        self._is_active = True
        self.btn_toggle.setText("Desativar Modo Acordado")
        self.status_card.setStyleSheet(
            "background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 16px;"
        )
        self.lbl_status_title.setText("Status: Ativo (Protegendo contra suspensão)")
        self.lbl_status_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #15803d;")

        if self.rb_timed.isChecked():
            preset_text = self.cmb_presets.currentText()
            minutes = 30
            if "30 minutos" in preset_text:
                minutes = 30
            elif "1 hora" in preset_text:
                minutes = 60
            elif "2 horas" in preset_text:
                minutes = 120
            elif "4 horas" in preset_text:
                minutes = 240
            elif "8 horas" in preset_text:
                minutes = 480
            elif "Personalizado" in preset_text:
                minutes = self.spin_minutes.value()

            total_seconds = minutes * 60
            self._target_end_time = time.time() + total_seconds
            self.lbl_timer_countdown.setVisible(True)
            self.lbl_timer_countdown.setText(f"Tempo restante: {format_remaining_seconds(total_seconds)}")
            self._countdown_timer.start()
        else:
            self._target_end_time = None
            self.lbl_timer_countdown.setVisible(False)

    def _deactivate(self) -> None:
        release_keep_awake()
        self._is_active = False
        self._target_end_time = None
        self._countdown_timer.stop()

        self.btn_toggle.setText("Ativar Modo Acordado")
        self.status_card.setStyleSheet(
            "background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px;"
        )
        self.lbl_status_title.setText("Status: Inativo")
        self.lbl_status_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #475569;")
        self.lbl_timer_countdown.setVisible(False)

    def _on_tick(self) -> None:
        if not self._is_active or self._target_end_time is None:
            return

        remaining = int(self._target_end_time - time.time())
        if remaining <= 0:
            self._deactivate()
        else:
            self.lbl_timer_countdown.setText(f"Tempo restante: {format_remaining_seconds(remaining)}")
