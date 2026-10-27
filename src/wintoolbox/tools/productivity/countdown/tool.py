"""
Interface de usuário para o Painel de Contagem Regressiva e Prazos com Widget Flutuante.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.countdown.logic import (
    CountdownItem,
    calculate_time_remaining,
    load_countdowns,
    save_countdowns,
)


class FloatingCountdownWidget(QWidget):
    """Widget flutuante minimalista 'Always on Top' para a área de trabalho."""

    def __init__(self, item: CountdownItem, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.item = item
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(260, 90)

        self._drag_pos = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.frame = QFrame()
        self.frame.setStyleSheet(
            f"QFrame {{ background-color: rgba(20, 20, 25, 0.92); border: 2px solid {item.color}; "
            "border-radius: 10px; padding: 8px; }"
        )
        vbox = QVBoxLayout(self.frame)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(4)

        top = QHBoxLayout()
        lbl_title = QLabel(f"<b>{item.title}</b>")
        lbl_title.setStyleSheet("color: white; font-size: 12px; border: none;")
        top.addWidget(lbl_title, 1)

        btn_close = QPushButton("×")
        btn_close.setFixedSize(18, 18)
        btn_close.setStyleSheet("background: transparent; color: #888; border: none; font-weight: bold;")
        btn_close.clicked.connect(self.close)
        top.addWidget(btn_close)
        vbox.addLayout(top)

        self.lbl_time = QLabel("Calculando...")
        self.lbl_time.setStyleSheet(f"color: {item.color}; font-size: 16px; font-weight: bold; border: none;")
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.lbl_time)

        layout.addWidget(self.frame)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_display)
        self.timer.start(1000)
        self._update_display()

    def _update_display(self) -> None:
        info = calculate_time_remaining(self.item.target_datetime)
        self.lbl_time.setText(info["formatted"])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


class CountdownEditDialog(QDialog):
    """Diálogo para criar ou editar uma contagem regressiva."""

    def __init__(self, item: Optional[CountdownItem] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Contagem Regressiva")
        self.resize(380, 260)
        self.item = item
        self.color = item.color if item else "#0284c7"

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_title = QLineEdit(item.title if item else "Novo Evento")
        form.addRow("Título do Evento:", self.txt_title)

        self.txt_category = QLineEdit(item.category if item else "Geral")
        form.addRow("Categoria:", self.txt_category)

        self.dt_target = QDateTimeEdit()
        self.dt_target.setCalendarPopup(True)
        self.dt_target.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        if item:
            self.dt_target.setDateTime(QDateTime.fromString(item.target_datetime, Qt.DateFormat.ISODate))
        else:
            self.dt_target.setDateTime(QDateTime.currentDateTime().addDays(7))
        form.addRow("Data e Hora Alvo:", self.dt_target)

        # Cor
        c_box = QHBoxLayout()
        self.lbl_color = QLabel("       ")
        self.lbl_color.setStyleSheet(f"background-color: {self.color}; border-radius: 4px; border: 1px solid #666;")
        btn_col = QPushButton("Selecionar Cor...")
        btn_col.clicked.connect(self._pick_color)
        c_box.addWidget(self.lbl_color)
        c_box.addWidget(btn_col)
        c_box.addStretch()
        form.addRow("Cor de Destaque:", c_box)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_canc = QPushButton("Cancelar")
        btn_canc.clicked.connect(self.reject)
        btn_ok = QPushButton("Salvar")
        btn_ok.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white;")
        btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_canc)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self.color), self, "Cor do Card")
        if c.isValid():
            self.color = c.name()
            self.lbl_color.setStyleSheet(f"background-color: {self.color}; border-radius: 4px; border: 1px solid #666;")

    def get_data(self) -> tuple[str, str, str, str]:
        title = self.txt_title.text().strip() or "Evento"
        cat = self.txt_category.text().strip() or "Geral"
        dt_str = self.dt_target.dateTime().toString(Qt.DateFormat.ISODate)
        return title, cat, dt_str, self.color


@register
class CountdownTool(Tool):
    """Painel de contagem regressiva para prazos e lançamentos com widget flutuante."""

    id = "productivity.countdown"
    name = "Painel de Contagem Regressiva"
    description = "Monitore prazos de entrega, lançamentos e aniversários com relógios visuais e widget flutuante minimalista."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "countdowns.json"
        self.countdowns: List[CountdownItem] = load_countdowns(self.storage_path)
        self.card_widgets: List[tuple[CountdownItem, QLabel]] = []
        self.floating_widgets: List[FloatingCountdownWidget] = []

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Painel de Contagem Regressiva")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Acompanhe o tempo exato restante até seus eventos importantes ou prazos críticos de projeto.")
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        btn_new = QPushButton("+ Nova Contagem")
        btn_new.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white; padding: 6px 14px;")
        btn_new.clicked.connect(self._on_new_countdown)
        top_bar.addWidget(btn_new)

        layout.addLayout(top_bar)

        # Grade de cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        # Timer global para atualizar labels a cada segundo
        self.timer = QTimer(widget)
        self.timer.timeout.connect(self._tick_updates)
        self.timer.start(1000)

        self._refresh_cards()
        return widget

    def _save_data(self) -> None:
        save_countdowns(self.countdowns, self.storage_path)

    def _refresh_cards(self) -> None:
        self.card_widgets.clear()
        while self.grid.count() > 0:
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        cols = 3
        for idx, item in enumerate(self.countdowns):
            row = idx // cols
            col = idx % cols
            card_widget, lbl_val = self._create_card(item)
            self.grid.addWidget(card_widget, row, col)
            self.card_widgets.append((item, lbl_val))

        self._tick_updates()

    def _create_card(self, item: CountdownItem) -> tuple[QWidget, QLabel]:
        card = QFrame()
        card.setFixedWidth(280)
        card.setStyleSheet(
            f"QFrame {{ background-color: rgba(128, 128, 128, 0.08); border-top: 4px solid {item.color}; "
            "border-radius: 8px; border-left: 1px solid rgba(128, 128, 128, 0.2); "
            "border-right: 1px solid rgba(128, 128, 128, 0.2); border-bottom: 1px solid rgba(128, 128, 128, 0.2); "
            "padding: 10px; }"
        )
        vbox = QVBoxLayout(card)
        vbox.setSpacing(8)

        # Título e Categoria
        lbl_cat = QLabel(item.category.upper())
        lbl_cat.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {item.color}; border: none;")
        vbox.addWidget(lbl_cat)

        lbl_t = QLabel(f"<b>{item.title}</b>")
        lbl_t.setStyleSheet("font-size: 15px; border: none;")
        lbl_t.setWordWrap(True)
        vbox.addWidget(lbl_t)

        # Display do tempo restante
        lbl_clock = QLabel("...")
        lbl_clock.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {item.color}; padding: 6px; "
            "background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; border: none;"
        )
        lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl_clock)

        # Data alvo
        try:
            dt = datetime.fromisoformat(item.target_datetime)
            dt_fmt = dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            dt_fmt = item.target_datetime
        lbl_target = QLabel(f"Data Alvo: {dt_fmt}")
        lbl_target.setStyleSheet("font-size: 11px; color: #888888; border: none;")
        vbox.addWidget(lbl_target)

        # Ações
        act_box = QHBoxLayout()
        act_box.setSpacing(6)

        btn_float = QPushButton("Flutuante")
        btn_float.setToolTip("Abrir mini-widget fixado na área de trabalho")
        btn_float.clicked.connect(lambda _, it=item: self._open_floating(it))
        act_box.addWidget(btn_float)

        btn_edit = QPushButton("Editar")
        btn_edit.clicked.connect(lambda _, it=item: self._on_edit_countdown(it))
        act_box.addWidget(btn_edit)

        btn_del = QPushButton("Excluir")
        btn_del.setStyleSheet("color: #dc2626;")
        btn_del.clicked.connect(lambda _, it=item: self._on_delete_countdown(it))
        act_box.addWidget(btn_del)

        vbox.addLayout(act_box)
        return card, lbl_clock

    def _tick_updates(self) -> None:
        for item, lbl in self.card_widgets:
            info = calculate_time_remaining(item.target_datetime)
            lbl.setText(info["formatted"])
            if info["is_past"]:
                lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #888888; padding: 6px; border: none;")
            else:
                lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {item.color}; padding: 6px; border: none;")

    def _open_floating(self, item: CountdownItem) -> None:
        w = FloatingCountdownWidget(item)
        self.floating_widgets.append(w)
        w.show()

    def _on_new_countdown(self) -> None:
        dlg = CountdownEditDialog(None)
        if dlg.exec():
            title, cat, dt_str, col = dlg.get_data()
            import uuid
            item = CountdownItem(
                id=str(uuid.uuid4()),
                title=title,
                category=cat,
                target_datetime=dt_str,
                color=col
            )
            self.countdowns.append(item)
            self._save_data()
            self._refresh_cards()

    def _on_edit_countdown(self, item: CountdownItem) -> None:
        dlg = CountdownEditDialog(item)
        if dlg.exec():
            title, cat, dt_str, col = dlg.get_data()
            item.title = title
            item.category = cat
            item.target_datetime = dt_str
            item.color = col
            self._save_data()
            self._refresh_cards()

    def _on_delete_countdown(self, item: CountdownItem) -> None:
        reply = QMessageBox.question(
            None,
            "Excluir Contagem",
            f"Deseja remover a contagem regressiva '{item.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.countdowns = [c for c in self.countdowns if c.id != item.id]
            self._save_data()
            self._refresh_cards()
