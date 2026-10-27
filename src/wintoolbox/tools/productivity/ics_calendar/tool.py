"""
Interface de usuário para o Visualizador e Gerenciador de Calendário iCalendar (.ics).
"""
from datetime import date
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.ics_calendar.logic import (
    CalendarEvent,
    load_events_from_ics,
    parse_ics_content,
    save_events_to_ics,
)


class EventEditDialog(QDialog):
    """Diálogo para criar ou editar evento de calendário."""

    def __init__(self, event: Optional[CalendarEvent] = None, default_date: Optional[QDate] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Evento")
        self.resize(420, 320)
        self.event = event

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_summary = QLineEdit(event.summary if event else "")
        form.addRow("Título do Evento:", self.txt_summary)

        ref_date = default_date or QDate.currentDate()
        self.dt_start = QDateTimeEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDisplayFormat("dd/MM/yyyy HH:mm")

        self.dt_end = QDateTimeEdit()
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setDisplayFormat("dd/MM/yyyy HH:mm")

        if event:
            self.dt_start.setDateTime(QDateTime.fromString(event.dtstart, Qt.DateFormat.ISODate))
            self.dt_end.setDateTime(QDateTime.fromString(event.dtend, Qt.DateFormat.ISODate))
        else:
            base_dt = QDateTime(ref_date, QDateTime.currentDateTime().time())
            self.dt_start.setDateTime(base_dt)
            self.dt_end.setDateTime(base_dt.addSecs(3600))

        form.addRow("Início:", self.dt_start)
        form.addRow("Término:", self.dt_end)

        self.txt_location = QLineEdit(event.location if event else "")
        form.addRow("Local / Link:", self.txt_location)

        self.txt_desc = QTextEdit(event.description if event else "")
        self.txt_desc.setMaximumHeight(80)
        form.addRow("Descrição / Pauta:", self.txt_desc)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_canc = QPushButton("Cancelar")
        btn_canc.clicked.connect(self.reject)
        btn_save = QPushButton("Salvar Evento")
        btn_save.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white;")
        btn_save.clicked.connect(self.accept)
        btns.addWidget(btn_canc)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def get_data(self) -> tuple[str, str, str, str, str]:
        summary = self.txt_summary.text().strip() or "Evento"
        start_str = self.dt_start.dateTime().toString(Qt.DateFormat.ISODate)
        end_str = self.dt_end.dateTime().toString(Qt.DateFormat.ISODate)
        loc = self.txt_location.text().strip()
        desc = self.txt_desc.toPlainText().strip()
        return summary, start_str, end_str, loc, desc


@register
class IcsCalendarTool(Tool):
    """Visualizador e gerenciador local de eventos de calendário no formato padrão iCalendar (.ics)."""

    id = "productivity.ics_calendar"
    name = "Visualizador de Calendário iCalendar (.ics)"
    description = "Abra, edite e crie compromissos no formato universal iCalendar (.ics) compatível com Outlook, Google e Apple Calendar."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "calendar_events.ics"
        self.events: List[CalendarEvent] = load_events_from_ics(self.storage_path)
        self.selected_date: str = date.today().isoformat()

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Visualizador de Calendário iCalendar (.ics)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Gerencie compromissos localmente no formato universal .ics sem sincronização de terceiros."
        )
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        btn_new = QPushButton("+ Novo Evento")
        btn_new.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white; padding: 6px 14px;")
        btn_new.clicked.connect(self._on_new_event)
        top_bar.addWidget(btn_new)

        btn_import = QPushButton("Importar .ics...")
        btn_import.clicked.connect(self._on_import_ics)
        top_bar.addWidget(btn_import)

        btn_export = QPushButton("Exportar .ics...")
        btn_export.clicked.connect(self._on_export_ics)
        top_bar.addWidget(btn_export)

        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lado Esquerdo: Navegação de Calendário
        left_box = QWidget()
        v_left = QVBoxLayout(left_box)
        v_left.setContentsMargins(0, 0, 0, 0)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._on_calendar_selection_changed)
        v_left.addWidget(self.calendar)

        self.lbl_all_count = QLabel(f"Total de {len(self.events)} evento(s) no calendário.")
        self.lbl_all_count.setStyleSheet("color: #888888; font-size: 11px;")
        v_left.addWidget(self.lbl_all_count)
        v_left.addStretch()

        splitter.addWidget(left_box)

        # Lado Direito: Tabela de Eventos do Dia
        right_box = QWidget()
        v_right = QVBoxLayout(right_box)
        v_right.setContentsMargins(10, 0, 0, 0)
        v_right.setSpacing(8)

        self.lbl_day_title = QLabel(f"Compromissos para: {self.selected_date}")
        self.lbl_day_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0284c7;")
        v_right.addWidget(self.lbl_day_title)

        self.tbl_events = QTableWidget(0, 4)
        self.tbl_events.setHorizontalHeaderLabels(["Horário", "Título", "Local", "Descrição"])
        self.tbl_events.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_events.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_events.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tbl_events.setColumnWidth(2, 140)
        self.tbl_events.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_events.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_events.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_right.addWidget(self.tbl_events, 1)

        # Ações
        act_box = QHBoxLayout()
        btn_edit = QPushButton("Editar Evento")
        btn_edit.clicked.connect(self._on_edit_event)
        act_box.addWidget(btn_edit)

        btn_del = QPushButton("Excluir Evento")
        btn_del.setStyleSheet("color: #dc2626;")
        btn_del.clicked.connect(self._on_delete_event)
        act_box.addWidget(btn_del)
        act_box.addStretch()

        v_right.addLayout(act_box)

        splitter.addWidget(right_box)
        splitter.setSizes([320, 580])
        layout.addWidget(splitter, 1)

        self._refresh_day_events()
        return widget

    def _save_data(self) -> None:
        save_events_to_ics(self.events, self.storage_path)
        self.lbl_all_count.setText(f"Total de {len(self.events)} evento(s) no calendário.")

    def _on_calendar_selection_changed(self) -> None:
        qdt = self.calendar.selectedDate()
        self.selected_date = qdt.toString("yyyy-MM-dd")
        self.lbl_day_title.setText(f"Compromissos para: {self.selected_date}")
        self._refresh_day_events()

    def _refresh_day_events(self) -> None:
        day_events = [e for e in self.events if e.dtstart.startswith(self.selected_date)]

        self.tbl_events.setRowCount(0)
        for ev in day_events:
            r = self.tbl_events.rowCount()
            self.tbl_events.insertRow(r)

            # Formata horário
            t_start = ev.dtstart.split("T")[1][:5] if "T" in ev.dtstart else "Dia Inteiro"
            t_end = ev.dtend.split("T")[1][:5] if "T" in ev.dtend else ""
            t_str = f"{t_start} - {t_end}" if t_end else t_start

            it_time = QTableWidgetItem(t_str)
            it_time.setData(Qt.ItemDataRole.UserRole, ev.uid)
            it_summary = QTableWidgetItem(ev.summary)
            it_loc = QTableWidgetItem(ev.location)
            it_desc = QTableWidgetItem(ev.description)

            self.tbl_events.setItem(r, 0, it_time)
            self.tbl_events.setItem(r, 1, it_summary)
            self.tbl_events.setItem(r, 2, it_loc)
            self.tbl_events.setItem(r, 3, it_desc)

    def _on_new_event(self) -> None:
        dlg = EventEditDialog(None, default_date=self.calendar.selectedDate())
        if dlg.exec():
            summary, start_str, end_str, loc, desc = dlg.get_data()
            import uuid
            new_ev = CalendarEvent(
                uid=str(uuid.uuid4()),
                summary=summary,
                dtstart=start_str,
                dtend=end_str,
                location=loc,
                description=desc
            )
            self.events.append(new_ev)
            self._save_data()
            self._refresh_day_events()

    def _on_edit_event(self) -> None:
        row = self.tbl_events.currentRow()
        if row < 0:
            return
        it = self.tbl_events.item(row, 0)
        if not it:
            return
        uid = it.data(Qt.ItemDataRole.UserRole)
        ev = next((e for e in self.events if e.uid == uid), None)
        if not ev:
            return

        dlg = EventEditDialog(ev, default_date=self.calendar.selectedDate())
        if dlg.exec():
            summary, start_str, end_str, loc, desc = dlg.get_data()
            ev.summary = summary
            ev.dtstart = start_str
            ev.dtend = end_str
            ev.location = loc
            ev.description = desc
            self._save_data()
            self._refresh_day_events()

    def _on_delete_event(self) -> None:
        row = self.tbl_events.currentRow()
        if row < 0:
            return
        it = self.tbl_events.item(row, 0)
        if not it:
            return
        uid = it.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            None,
            "Excluir Evento",
            "Deseja realmente remover este evento do calendário?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.events = [e for e in self.events if e.uid != uid]
            self._save_data()
            self._refresh_day_events()

    def _on_import_ics(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Importar Calendário iCal", "", "iCalendar (*.ics)")
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                imported = parse_ics_content(content)
                self.events.extend(imported)
                self._save_data()
                self._refresh_day_events()
                QMessageBox.information(None, "Sucesso", f"{len(imported)} eventos importados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao importar .ics:\n{e}")

    def _on_export_ics(self) -> None:
        path, _ = QFileDialog.getSaveFileName(None, "Exportar Calendário", "calendario.ics", "iCalendar (*.ics)")
        if path:
            try:
                save_events_to_ics(self.events, Path(path))
                QMessageBox.information(None, "Sucesso", "Calendário exportado com sucesso no padrão .ics!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar:\n{e}")
