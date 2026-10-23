"""
Interface gráfica da ferramenta Alarmes e Lembretes.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QDate, QTime, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QTimeEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.reminders.logic import (
    REPEAT_MODES, add_reminder, check_due_reminders, delete_reminder,
    list_reminders, toggle_reminder_active
)
from wintoolbox.ui.tray import notify
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("productivity.reminders.ui")


@register
class RemindersTool(Tool):
    id = "productivity.reminders"
    name = "Alarmes e Lembretes"
    category = "Produtividade"
    description = "Agendamento de lembretes e alarmes com notificações nativas na área de trabalho do Windows"
    keywords = ["lembrete", "alarme", "notificacao", "aviso", "compromisso", "agenda", "produtividade"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RemindersView(self, parent)


class RemindersView(QWidget):
    def __init__(self, tool: RemindersTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._reminders: List[Dict[str, Any]] = []

        self._check_timer = QTimer(self)
        self._check_timer.setInterval(5000)  # Checa a cada 5 segundos
        self._check_timer.timeout.connect(self._check_due_events)
        self._check_timer.start()

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Alarmes e Lembretes",
            "Crie lembretes pontuais ou recorrentes que alertam através de notificações nativas do Windows."
        ))

        # 1. Formulário de Novo Lembrete
        form_box = QGroupBox("Criar Novo Lembrete")
        grid = QGridLayout(form_box)
        grid.setSpacing(8)

        grid.addWidget(QLabel("Título:"), 0, 0)
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("Ex: Reunião de alinhamento, beber água, enviar e-mail...")
        grid.addWidget(self.edit_title, 0, 1, 1, 3)

        grid.addWidget(QLabel("Mensagem / Detalhes:"), 1, 0)
        self.edit_msg = QLineEdit()
        self.edit_msg.setPlaceholderText("Opcional: detalhes adicionais do aviso")
        grid.addWidget(self.edit_msg, 1, 1, 1, 3)

        # Data e Hora
        grid.addWidget(QLabel("Data:"), 2, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        grid.addWidget(self.date_edit, 2, 1)

        grid.addWidget(QLabel("Horário:"), 2, 2)
        self.time_edit = QTimeEdit()
        # Horário padrão: agora + 15 min
        future_time = datetime.now() + timedelta(minutes=15)
        self.time_edit.setTime(QTime(future_time.hour, future_time.minute))
        grid.addWidget(self.time_edit, 2, 3)

        # Atalhos rápidos de tempo
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("Adicionar rápido:"))
        btn_15m = QPushButton("+15 min")
        btn_15m.clicked.connect(lambda: self._add_minutes_to_time(15))
        btn_30m = QPushButton("+30 min")
        btn_30m.clicked.connect(lambda: self._add_minutes_to_time(30))
        btn_1h = QPushButton("+1 hora")
        btn_1h.clicked.connect(lambda: self._add_minutes_to_time(60))
        quick_row.addWidget(btn_15m)
        quick_row.addWidget(btn_30m)
        quick_row.addWidget(btn_1h)
        quick_row.addStretch(1)
        grid.addLayout(quick_row, 3, 0, 1, 2)

        # Repetição
        grid.addWidget(QLabel("Repetição:"), 3, 2)
        self.combo_repeat = QComboBox()
        for key, label in REPEAT_MODES.items():
            self.combo_repeat.addItem(label, key)
        grid.addWidget(self.combo_repeat, 3, 3)

        # Botão Salvar
        btn_save = QPushButton("Salvar Lembrete")
        btn_save.setProperty("class", "primary")
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._on_save_reminder)
        grid.addWidget(btn_save, 4, 3, alignment=Qt.AlignmentFlag.AlignRight)

        root.addWidget(form_box)

        # 2. Lista de Lembretes
        list_box = QGroupBox("Lembretes Agendados")
        list_layout = QVBoxLayout(list_box)
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(6)
        list_layout.addWidget(self.list_widget)
        root.addWidget(list_box, stretch=1)

    def _add_minutes_to_time(self, minutes: int) -> None:
        target = datetime.now() + timedelta(minutes=minutes)
        self.date_edit.setDate(QDate(target.year, target.month, target.day))
        self.time_edit.setTime(QTime(target.hour, target.minute))

    def _on_save_reminder(self) -> None:
        title = self.edit_title.text().strip()
        if not title:
            show_toast(self, "Digite um título para o lembrete.")
            return

        msg = self.edit_msg.text().strip()
        q_date = self.date_edit.date()
        q_time = self.time_edit.time()
        target_dt = datetime(q_date.year(), q_date.month(), q_date.day(), q_time.hour(), q_time.minute(), 0)

        if target_dt <= datetime.now():
            show_toast(self, "O horário do lembrete deve ser no futuro.", duration_ms=2500)
            return

        rep = self.combo_repeat.currentData() or "none"

        try:
            add_reminder(title=title, target_time=target_dt, message=msg, repeat_mode=rep)
            self.edit_title.clear()
            self.edit_msg.clear()
            self._refresh_list()
            show_toast(self, f"Lembrete agendado para {target_dt.strftime('%d/%m/%Y às %H:%M')}!")
        except Exception as exc:
            show_toast(self, f"Erro ao agendar: {exc}")

    def _refresh_list(self) -> None:
        self._reminders = list_reminders(include_inactive=True)
        self.list_widget.clear()

        for rem in self._reminders:
            item = QListWidgetItem()
            widget = self._create_reminder_widget(rem)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _create_reminder_widget(self, data: Dict[str, Any]) -> QWidget:
        container = QFrame()
        container.setProperty("class", "card")
        container.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 6px; }")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Informações
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)

        lbl_title = QLabel(data["title"])
        lbl_title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        if not data["is_active"]:
            lbl_title.setStyleSheet("color: rgba(255, 255, 255, 0.4);")
        text_layout.addWidget(lbl_title)

        try:
            dt_str = datetime.fromisoformat(data["target_time"]).strftime("%d/%m/%Y %H:%M")
        except Exception:
            dt_str = data["target_time"]

        rep_label = REPEAT_MODES.get(data["repeat_mode"], "Uma vez")
        status_str = "Ativo" if data["is_active"] else ("Disparado / Concluído" if data["triggered"] else "Pausado")

        lbl_meta = QLabel(f"Horário: {dt_str}  •  Repetição: {rep_label}  •  Status: {status_str}")
        lbl_meta.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11px;")
        text_layout.addWidget(lbl_meta)

        if data["message"]:
            lbl_msg = QLabel(data["message"])
            lbl_msg.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
            text_layout.addWidget(lbl_msg)

        layout.addLayout(text_layout, stretch=1)

        # Ações
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        btn_toggle = QPushButton("Pausar" if data["is_active"] else "Ativar")
        btn_toggle.setFixedWidth(75)
        btn_toggle.clicked.connect(lambda checked=False, r_id=data["id"]: self._toggle_active(r_id))
        actions_layout.addWidget(btn_toggle)

        btn_del = QPushButton("Excluir")
        btn_del.setFixedWidth(65)
        btn_del.clicked.connect(lambda checked=False, r_id=data["id"]: self._delete_reminder(r_id))
        actions_layout.addWidget(btn_del)

        layout.addLayout(actions_layout)
        return container

    def _toggle_active(self, reminder_id: int) -> None:
        toggle_reminder_active(reminder_id)
        self._refresh_list()

    def _delete_reminder(self, reminder_id: int) -> None:
        delete_reminder(reminder_id)
        self._refresh_list()

    def _check_due_events(self) -> None:
        due = check_due_reminders()
        if due:
            self._refresh_list()
            for r in due:
                title = r["title"]
                msg = r["message"] or "Horário do lembrete programado atingido!"
                notify(f"Lembrete: {title}", msg)
                show_toast(self, f"Lembrete: {title}", duration_ms=5000)
