"""
Interface gráfica do Autoclicker Automático.
"""
from typing import Optional, Tuple
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.autoclicker.logic import (
    get_cursor_position, perform_mouse_click
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("automation.autoclicker.ui")


@register
class AutoclickerTool(Tool):
    id = "automation.autoclicker"
    name = "Autoclicker Automático"
    category = "Automação"
    description = "Simulação contínua e repetitiva de cliques de mouse com intervalos configuráveis e coordenadas fixas"
    keywords = ["autoclicker", "mouse", "clique", "macro", "repetir", "automacao", "fps"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return AutoclickerView(self, parent)


class AutoclickerView(QWidget):
    def __init__(self, tool: AutoclickerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._is_running = False
        self._clicks_done = 0

        # Timer de execução dos cliques
        self._click_timer = QTimer(self)
        self._click_timer.timeout.connect(self._execute_click)

        # Timer de atualização das coordenadas do mouse
        self._pos_timer = QTimer(self)
        self._pos_timer.setInterval(200)
        self._pos_timer.timeout.connect(self._update_mouse_pos_label)
        self._pos_timer.start()

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Autoclicker Automático",
            "Automatize tarefas repetitivas com controle exato de frequência de cliques e posicionamento na tela."
        ))

        # 1. Intervalo entre Cliques
        interval_box = QGroupBox("Intervalo de Tempo entre Cliques")
        grid_time = QGridLayout(interval_box)
        grid_time.setSpacing(8)

        grid_time.addWidget(QLabel("Horas:"), 0, 0)
        self.spin_hours = QSpinBox()
        self.spin_hours.setRange(0, 24)
        grid_time.addWidget(self.spin_hours, 0, 1)

        grid_time.addWidget(QLabel("Minutos:"), 0, 2)
        self.spin_mins = QSpinBox()
        self.spin_mins.setRange(0, 59)
        grid_time.addWidget(self.spin_mins, 0, 3)

        grid_time.addWidget(QLabel("Segundos:"), 0, 4)
        self.spin_secs = QSpinBox()
        self.spin_secs.setRange(0, 59)
        grid_time.addWidget(self.spin_secs, 0, 5)

        grid_time.addWidget(QLabel("Milissegundos (ms):"), 0, 6)
        self.spin_ms = QSpinBox()
        self.spin_ms.setRange(10, 999)
        self.spin_ms.setValue(100)
        grid_time.addWidget(self.spin_ms, 0, 7)

        root.addWidget(interval_box)

        # 2. Configurações do Clique
        opts_box = QGroupBox("Opções do Clique")
        grid_opts = QGridLayout(opts_box)
        grid_opts.setSpacing(8)

        grid_opts.addWidget(QLabel("Botão do Mouse:"), 0, 0)
        self.combo_button = QComboBox()
        self.combo_button.addItem("Botão Esquerdo (Padrão)", "left")
        self.combo_button.addItem("Botão Direito", "right")
        self.combo_button.addItem("Botão Central / Scroll", "middle")
        grid_opts.addWidget(self.combo_button, 0, 1)

        grid_opts.addWidget(QLabel("Tipo do Clique:"), 0, 2)
        self.combo_click_type = QComboBox()
        self.combo_click_type.addItem("Clique Simples", "single")
        self.combo_click_type.addItem("Clique Duplo", "double")
        grid_opts.addWidget(self.combo_click_type, 0, 3)

        root.addWidget(opts_box)

        # 3. Posição do Mouse
        pos_box = QGroupBox("Localização do Clique")
        grid_pos = QGridLayout(pos_box)
        grid_pos.setSpacing(8)

        self.radio_current_pos = QRadioButton("Onde o cursor estiver (Posição Atual)")
        self.radio_current_pos.setChecked(True)
        self.radio_current_pos.toggled.connect(self._toggle_pos_mode)
        grid_pos.addWidget(self.radio_current_pos, 0, 0, 1, 2)

        self.radio_fixed_pos = QRadioButton("Coordenadas Fixas:")
        self.radio_fixed_pos.toggled.connect(self._toggle_pos_mode)
        grid_pos.addWidget(self.radio_fixed_pos, 1, 0)

        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("X:"))
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 10000)
        self.spin_x.setEnabled(False)
        coord_row.addWidget(self.spin_x)

        coord_row.addWidget(QLabel("Y:"))
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 10000)
        self.spin_y.setEnabled(False)
        coord_row.addWidget(self.spin_y)

        btn_capture = QPushButton("Capturar Posição Atual")
        btn_capture.clicked.connect(self._capture_coords)
        coord_row.addWidget(btn_capture)
        coord_row.addStretch(1)

        grid_pos.addLayout(coord_row, 1, 1)

        # Label de coordenadas do mouse ao vivo
        self.lbl_live_pos = QLabel("Cursor Atual: X = 0, Y = 0")
        self.lbl_live_pos.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11px;")
        grid_pos.addWidget(self.lbl_live_pos, 2, 0, 1, 2)

        root.addWidget(pos_box)

        # 4. Condição de Repetição
        repeat_box = QGroupBox("Condição de Parada")
        rep_layout = QHBoxLayout(repeat_box)

        self.radio_infinite = QRadioButton("Repetir infinitamente até clicar em Parar")
        self.radio_infinite.setChecked(True)
        rep_layout.addWidget(self.radio_infinite)

        self.radio_count = QRadioButton("Parar após número de vezes:")
        rep_layout.addWidget(self.radio_count)

        self.spin_repeat_count = QSpinBox()
        self.spin_repeat_count.setRange(1, 1000000)
        self.spin_repeat_count.setValue(100)
        rep_layout.addWidget(self.spin_repeat_count)
        rep_layout.addStretch(1)

        root.addWidget(repeat_box)

        # 5. Painel de Execução
        run_frame = QFrame()
        run_frame.setProperty("class", "card")
        run_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 12px; }")
        run_layout = QHBoxLayout(run_frame)

        self.lbl_status = QLabel("Status: Parado")
        self.lbl_status.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        run_layout.addWidget(self.lbl_status)
        run_layout.addStretch(1)

        self.btn_toggle = QPushButton("Iniciar Autoclicker")
        self.btn_toggle.setProperty("class", "primary")
        self.btn_toggle.setFixedSize(160, 40)
        self.btn_toggle.clicked.connect(self._toggle_autoclicker)
        run_layout.addWidget(self.btn_toggle)

        root.addWidget(run_frame)
        root.addStretch(1)

    def _toggle_pos_mode(self) -> None:
        is_fixed = self.radio_fixed_pos.isChecked()
        self.spin_x.setEnabled(is_fixed)
        self.spin_y.setEnabled(is_fixed)

    def _capture_coords(self) -> None:
        x, y = get_cursor_position()
        self.spin_x.setValue(x)
        self.spin_y.setValue(y)
        self.radio_fixed_pos.setChecked(True)
        show_toast(self, f"Coordenadas capturadas: ({x}, {y})")

    def _update_mouse_pos_label(self) -> None:
        x, y = get_cursor_position()
        self.lbl_live_pos.setText(f"Cursor Atual na Tela: X = {x}, Y = {y}")

    def _get_interval_ms(self) -> int:
        h = self.spin_hours.value()
        m = self.spin_mins.value()
        s = self.spin_secs.value()
        ms = self.spin_ms.value()
        total_ms = (h * 3600000) + (m * 60000) + (s * 1000) + ms
        return max(10, total_ms)

    def _toggle_autoclicker(self) -> None:
        if self._is_running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        self._is_running = True
        self._clicks_done = 0
        interval = self._get_interval_ms()

        self._click_timer.setInterval(interval)
        self._click_timer.start()

        self.btn_toggle.setText("Parar Autoclicker")
        self.btn_toggle.setStyleSheet("background-color: #EF4444; color: white;")
        self.lbl_status.setText(f"Status: Executando a cada {interval} ms...")
        self.lbl_status.setStyleSheet("color: #10B981; font-weight: bold;")

    def _stop(self) -> None:
        self._is_running = False
        self._click_timer.stop()

        self.btn_toggle.setText("Iniciar Autoclicker")
        self.btn_toggle.setStyleSheet("")
        self.lbl_status.setText(f"Status: Parado ({self._clicks_done} cliques efetuados)")
        self.lbl_status.setStyleSheet("color: rgba(255, 255, 255, 0.6);")

    def _execute_click(self) -> None:
        if not self._is_running:
            return

        button = self.combo_button.currentData() or "left"
        click_type = self.combo_click_type.currentData() or "single"

        coords = None
        if self.radio_fixed_pos.isChecked():
            coords = (self.spin_x.value(), self.spin_y.value())

        perform_mouse_click(button=button, click_type=click_type, coords=coords)
        self._clicks_done += 1

        # Checa parada por contagem
        if self.radio_count.isChecked() and self._clicks_done >= self.spin_repeat_count.value():
            self._stop()
            show_toast(self, f"Autoclicker finalizou {self._clicks_done} cliques!")

    def hideEvent(self, event) -> None:
        # Segurança: se o usuário trocar de ferramenta, para o autoclicker
        if self._is_running:
            self._stop()
        super().hideEvent(event)
