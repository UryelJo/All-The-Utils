"""
Interface gráfica do Timer Pomodoro de Foco.
"""
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.pomodoro.logic import (
    MODE_FOCUS, MODE_LABELS, MODE_LONG_BREAK, MODE_SHORT_BREAK,
    PomodoroConfig, PomodoroManager
)
from wintoolbox.ui.tray import notify
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("productivity.pomodoro.ui")


@register
class PomodoroTool(Tool):
    id = "productivity.pomodoro"
    name = "Timer Pomodoro"
    category = "Produtividade"
    description = "Temporizador Pomodoro de produtividade: gerencia ciclos de foco intenso (25 min) intercalados com pausas curtas e longas com alertas sonoros."
    keywords = ["pomodoro", "timer", "foco", "concentracao", "pausa", "tempo", "produtividade"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PomodoroView(self, parent)


class PomodoroView(QWidget):
    def __init__(self, tool: PomodoroTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.manager = PomodoroManager()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timer_tick)

        self._build_ui()
        self._update_display()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        root.addWidget(ToolHeader(
            "Timer Pomodoro de Foco",
            "Trabalhe em blocos cronometrados com máxima energia e mantenha a consistência com pausas regulares."
        ))

        # Card Principal Central
        main_card = QFrame()
        main_card.setProperty("class", "card")
        main_card.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 20px; }")

        card_layout = QVBoxLayout(main_card)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Nome do Modo
        self.lbl_mode = QLabel("Foco no Trabalho")
        self.lbl_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #60A5FA;")
        card_layout.addWidget(self.lbl_mode, alignment=Qt.AlignmentFlag.AlignCenter)

        # Relógio Digital Grande
        self.lbl_clock = QLabel("25:00")
        self.lbl_clock.setFont(QFont("Cascadia Mono", 48, QFont.Weight.Bold))
        card_layout.addWidget(self.lbl_clock, alignment=Qt.AlignmentFlag.AlignCenter)

        # Barra de Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(360)
        card_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Indicador de Ciclos e Tempo Acumulado
        self.lbl_stats = QLabel("Ciclos Concluídos: 0  |  Tempo Focado: 0 min")
        self.lbl_stats.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        card_layout.addWidget(self.lbl_stats, alignment=Qt.AlignmentFlag.AlignCenter)

        # Botões de Ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_toggle = QPushButton("Iniciar Foco")
        self.btn_toggle.setProperty("class", "primary")
        self.btn_toggle.setFixedWidth(140)
        self.btn_toggle.setFixedHeight(36)
        self.btn_toggle.clicked.connect(self._toggle_run)
        btn_layout.addWidget(self.btn_toggle)

        self.btn_reset = QPushButton("Reiniciar")
        self.btn_reset.setFixedWidth(100)
        self.btn_reset.setFixedHeight(36)
        self.btn_reset.clicked.connect(self._reset)
        btn_layout.addWidget(self.btn_reset)

        self.btn_skip = QPushButton("Pular Etapa")
        self.btn_skip.setFixedWidth(110)
        self.btn_skip.setFixedHeight(36)
        self.btn_skip.clicked.connect(self._skip)
        btn_layout.addWidget(self.btn_skip)

        card_layout.addLayout(btn_layout)
        root.addWidget(main_card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Painel de Ajustes de Duração
        cfg_box = QGroupBox("Configurações dos Ciclos (Minutos)")
        cfg_layout = QGridLayout(cfg_box)
        cfg_layout.setSpacing(10)

        cfg_layout.addWidget(QLabel("Tempo de Foco:"), 0, 0)
        self.spin_focus = QSpinBox()
        self.spin_focus.setRange(1, 120)
        self.spin_focus.setValue(25)
        self.spin_focus.valueChanged.connect(self._on_durations_changed)
        cfg_layout.addWidget(self.spin_focus, 0, 1)

        cfg_layout.addWidget(QLabel("Pausa Curta:"), 0, 2)
        self.spin_short = QSpinBox()
        self.spin_short.setRange(1, 60)
        self.spin_short.setValue(5)
        self.spin_short.valueChanged.connect(self._on_durations_changed)
        cfg_layout.addWidget(self.spin_short, 0, 3)

        cfg_layout.addWidget(QLabel("Pausa Longa:"), 0, 4)
        self.spin_long = QSpinBox()
        self.spin_long.setRange(1, 90)
        self.spin_long.setValue(15)
        self.spin_long.valueChanged.connect(self._on_durations_changed)
        cfg_layout.addWidget(self.spin_long, 0, 5)

        root.addWidget(cfg_box)
        root.addStretch(1)

    def _toggle_run(self) -> None:
        if self.manager.is_running:
            self.manager.pause()
            self._timer.stop()
            self.btn_toggle.setText("Continuar")
        else:
            self.manager.start()
            self._timer.start()
            self.btn_toggle.setText("Pausar")

    def _reset(self) -> None:
        self.manager.reset_current_mode()
        self._timer.stop()
        self.btn_toggle.setText("Iniciar")
        self._update_display()

    def _skip(self) -> None:
        self.manager.skip_to_next_phase()
        self._timer.stop()
        self.btn_toggle.setText("Iniciar")
        self._update_display()

    def _on_durations_changed(self) -> None:
        self.manager.set_durations(
            self.spin_focus.value(),
            self.spin_short.value(),
            self.spin_long.value()
        )
        self._update_display()

    def _on_timer_tick(self) -> None:
        finished, msg = self.manager.tick(step_seconds=1)
        self._update_display()

        if finished and msg:
            self._timer.stop()
            self.btn_toggle.setText("Iniciar Próxima Etapa")
            show_toast(self, msg, duration_ms=4000)
            notify("WinToolbox — Pomodoro", msg)

    def _update_display(self) -> None:
        # Texto do Relógio
        self.lbl_clock.setText(self.manager.format_time(self.manager.remaining_seconds))

        # Título e Cor do Modo
        mode = self.manager.mode
        label = MODE_LABELS.get(mode, "Foco")
        self.lbl_mode.setText(label)

        if mode == MODE_FOCUS:
            self.lbl_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #60A5FA;")
        elif mode == MODE_SHORT_BREAK:
            self.lbl_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #34D399;")
        else:
            self.lbl_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #A78BFA;")

        # Barra de Progresso (0 a 1000)
        pct = int(self.manager.get_progress_percentage() * 1000)
        self.progress_bar.setValue(pct)

        # Estatísticas
        focus_mins = self.manager.total_focus_seconds // 60
        self.lbl_stats.setText(
            f"Ciclos Concluídos: {self.manager.cycles_completed}  |  Tempo Focado: {focus_mins} min"
        )
