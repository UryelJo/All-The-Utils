"""
Interface de usuário para o Assistente de Ergonomia e Pausas Ativas.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.break_reminder.logic import (
    ReminderProfile,
    format_countdown,
    get_random_tip,
    load_reminder_profile,
    save_reminder_profile,
)


class BreakPopupDialog(QDialog):
    """Janela de pausa ergonômica com contagem de descanso e dicas de saúde."""

    def __init__(self, title: str, tip: str, duration_sec: int = 20, parent=None):
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hora da Pausa Ativa!")
        self.resize(380, 220)
        self.duration_sec = duration_sec
        self.remaining_sec = duration_sec

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_t = QLabel(f"<b>{title}</b>")
        lbl_t.setStyleSheet("font-size: 16px; color: #0284c7;")
        layout.addWidget(lbl_t)

        lbl_tip = QLabel(tip)
        lbl_tip.setWordWrap(True)
        lbl_tip.setStyleSheet("font-size: 13px; color: #334155;")
        layout.addWidget(lbl_tip, 1)

        self.lbl_timer = QLabel(format_countdown(self.remaining_sec))
        self.lbl_timer.setStyleSheet("font-size: 24px; font-weight: bold; color: #16a34a;")
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_timer)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_done = QPushButton("Concluir Pausa")
        btn_done.setStyleSheet("font-weight: bold; background-color: #16a34a; color: white; padding: 6px 14px;")
        btn_done.clicked.connect(self.accept)
        btn_box.addWidget(btn_done)
        layout.addLayout(btn_box)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self) -> None:
        self.remaining_sec -= 1
        if self.remaining_sec <= 0:
            self.lbl_timer.setText("Pausa Concluída!")
            self.timer.stop()
        else:
            self.lbl_timer.setText(format_countdown(self.remaining_sec))


@register
class BreakReminderTool(Tool):
    """Assistente de ergonomia no computador para incentivo a pausas ativas e hidratação."""

    id = "productivity.break_reminder"
    name = "Assistente de Ergonomia e Pausas Ativas"
    description = "Proteja sua visão e postura com a regra 20-20-20, lembretes de alongamento e hidratação regular."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "break_reminder.json"
        self.profile: ReminderProfile = load_reminder_profile(self.storage_path)

        # Contadores de segundos restantes
        self.eye_sec = self.profile.eye_interval_min * 60
        self.stretch_sec = self.profile.stretch_interval_min * 60
        self.water_sec = self.profile.water_interval_min * 60
        self.is_running = False

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Top Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Assistente de Ergonomia e Pausas Ativas")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Pequenas pausas regulares previnem a síndrome da visão de computador (CVS), "
            "lesões por esforço repetitivo (LER) e fadiga postural."
        )
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        self.btn_toggle = QPushButton("Iniciar Monitoramento")
        self.btn_toggle.setStyleSheet("font-weight: bold; background-color: #16a34a; color: white; padding: 8px 16px;")
        self.btn_toggle.clicked.connect(self._toggle_monitoring)
        top_bar.addWidget(self.btn_toggle)

        layout.addLayout(top_bar)

        # Cartões de Lembretes (Cards lado a lado)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # 1. Regra 20-20-20 (Olhos)
        self.card_eye, self.lbl_clock_eye = self._create_reminder_card(
            "👀 Descanso Visual (20-20-20)",
            "#0284c7",
            "A cada 20 minutos, olhe para 6 metros por 20 segundos.",
            self.eye_sec
        )
        cards_layout.addWidget(self.card_eye)

        # 2. Alongamento Físico
        self.card_stretch, self.lbl_clock_stretch = self._create_reminder_card(
            "🧘 Alongamento & Postura",
            "#ea580c",
            "Relaxe pescoço, ombros e coluna para evitar tensões.",
            self.stretch_sec
        )
        cards_layout.addWidget(self.card_stretch)

        # 3. Hidratação
        self.card_water, self.lbl_clock_water = self._create_reminder_card(
            "💧 Beber Água (Hidratação)",
            "#06b6d4",
            "Tome um copo d'água para manter a hidratação e o foco.",
            self.water_sec
        )
        cards_layout.addWidget(self.card_water)

        layout.addLayout(cards_layout)

        # Configurações de Intervalos
        grp_settings = QFrame()
        grp_settings.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 12px; }"
        )
        v_sett = QVBoxLayout(grp_settings)
        v_sett.addWidget(QLabel("<b>Configuração de Intervalos Personalizados:</b>"))

        form = QFormLayout()

        # Olhos
        box_eye = QHBoxLayout()
        self.chk_eye = QCheckBox("Habilitar")
        self.chk_eye.setChecked(self.profile.eye_enabled)
        self.spn_eye = QSpinBox()
        self.spn_eye.setRange(5, 120)
        self.spn_eye.setValue(self.profile.eye_interval_min)
        self.spn_eye.setSuffix(" minutos")
        box_eye.addWidget(self.chk_eye)
        box_eye.addWidget(self.spn_eye)
        box_eye.addStretch()
        form.addRow("Descanso Ocular:", box_eye)

        # Alongamento
        box_stretch = QHBoxLayout()
        self.chk_stretch = QCheckBox("Habilitar")
        self.chk_stretch.setChecked(self.profile.stretch_enabled)
        self.spn_stretch = QSpinBox()
        self.spn_stretch.setRange(10, 180)
        self.spn_stretch.setValue(self.profile.stretch_interval_min)
        self.spn_stretch.setSuffix(" minutos")
        box_stretch.addWidget(self.chk_stretch)
        box_stretch.addWidget(self.spn_stretch)
        box_stretch.addStretch()
        form.addRow("Alongamento:", box_stretch)

        # Água
        box_water = QHBoxLayout()
        self.chk_water = QCheckBox("Habilitar")
        self.chk_water.setChecked(self.profile.water_enabled)
        self.spn_water = QSpinBox()
        self.spn_water.setRange(15, 240)
        self.spn_water.setValue(self.profile.water_interval_min)
        self.spn_water.setSuffix(" minutos")
        box_water.addWidget(self.chk_water)
        box_water.addWidget(self.spn_water)
        box_water.addStretch()
        form.addRow("Hidratação:", box_water)

        v_sett.addLayout(form)

        btn_save_sett = QPushButton("Salvar Preferências")
        btn_save_sett.clicked.connect(self._save_settings)
        v_sett.addWidget(btn_save_sett, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(grp_settings)

        # Timer operacional
        self.timer = QTimer(widget)
        self.timer.timeout.connect(self._on_tick)

        layout.addStretch()
        return widget

    def _create_reminder_card(self, title: str, color: str, desc: str, initial_sec: int) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: rgba(128, 128, 128, 0.08); border-top: 4px solid {color}; "
            "border-radius: 8px; padding: 12px; }"
        )
        vbox = QVBoxLayout(frame)
        vbox.setSpacing(6)

        lbl_t = QLabel(f"<b>{title}</b>")
        lbl_t.setStyleSheet("font-size: 14px; border: none;")
        vbox.addWidget(lbl_t)

        lbl_d = QLabel(desc)
        lbl_d.setStyleSheet("color: #888888; font-size: 11px; border: none;")
        lbl_d.setWordWrap(True)
        vbox.addWidget(lbl_d)

        lbl_clock = QLabel(format_countdown(initial_sec))
        lbl_clock.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {color}; padding: 8px; "
            "background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; border: none;"
        )
        lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl_clock)

        btn_test = QPushButton("Testar Pausa")
        btn_test.clicked.connect(lambda _, t=title: self._trigger_break_popup(t))
        vbox.addWidget(btn_test)

        return frame, lbl_clock

    def _toggle_monitoring(self) -> None:
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.btn_toggle.setText("Iniciar Monitoramento")
            self.btn_toggle.setStyleSheet("font-weight: bold; background-color: #16a34a; color: white; padding: 8px 16px;")
        else:
            self.timer.start(1000)
            self.is_running = True
            self.btn_toggle.setText("Pausar Monitoramento")
            self.btn_toggle.setStyleSheet("font-weight: bold; background-color: #dc2626; color: white; padding: 8px 16px;")

    def _on_tick(self) -> None:
        if self.profile.eye_enabled:
            self.eye_sec -= 1
            if self.eye_sec <= 0:
                self.eye_sec = self.profile.eye_interval_min * 60
                self._trigger_break_popup("👀 Descanso Visual (Regra 20-20-20)", "eye")
            self.lbl_clock_eye.setText(format_countdown(self.eye_sec))

        if self.profile.stretch_enabled:
            self.stretch_sec -= 1
            if self.stretch_sec <= 0:
                self.stretch_sec = self.profile.stretch_interval_min * 60
                self._trigger_break_popup("🧘 Pausa para Alongamento", "stretch")
            self.lbl_clock_stretch.setText(format_countdown(self.stretch_sec))

        if self.profile.water_enabled:
            self.water_sec -= 1
            if self.water_sec <= 0:
                self.water_sec = self.profile.water_interval_min * 60
                self._trigger_break_popup("💧 Hora de se Hidratar", "water")
            self.lbl_clock_water.setText(format_countdown(self.water_sec))

    def _trigger_break_popup(self, title: str, rem_type: str = "stretch") -> None:
        tip = get_random_tip(rem_type)
        dlg = BreakPopupDialog(title, tip, duration_sec=20)
        dlg.exec()

    def _save_settings(self) -> None:
        self.profile.eye_enabled = self.chk_eye.isChecked()
        self.profile.eye_interval_min = self.spn_eye.value()
        self.profile.stretch_enabled = self.chk_stretch.isChecked()
        self.profile.stretch_interval_min = self.spn_stretch.value()
        self.profile.water_enabled = self.chk_water.isChecked()
        self.profile.water_interval_min = self.spn_water.value()

        save_reminder_profile(self.profile, self.storage_path)

        self.eye_sec = self.profile.eye_interval_min * 60
        self.stretch_sec = self.profile.stretch_interval_min * 60
        self.water_sec = self.profile.water_interval_min * 60

        self.lbl_clock_eye.setText(format_countdown(self.eye_sec))
        self.lbl_clock_stretch.setText(format_countdown(self.stretch_sec))
        self.lbl_clock_water.setText(format_countdown(self.water_sec))

        QMessageBox.information(None, "Preferências Salvas", "Configurações de ergonomia atualizadas com sucesso!")
