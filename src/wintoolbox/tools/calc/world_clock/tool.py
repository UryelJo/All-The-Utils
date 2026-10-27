"""
Interface gráfica do Relógio Mundial e Conversor de Fusos.
"""
from datetime import datetime
from typing import Optional
from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateTimeEdit, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.world_clock.logic import (
    POPULAR_TIMEZONES, convert_time_between_zones, get_all_world_clocks
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

_log = get_logger("calc.world_clock.ui")


@register
class WorldClockTool(Tool):
    id = "calc.world_clock"
    name = "Relógio Mundial"
    category = "Calculadoras"
    description = "Relógio mundial em tempo real das principais capitais do mundo, conversor de fusos horários (UTC/GMT), horário de verão e comparativo de jornadas de trabalho."
    keywords = ["relogio", "fuso", "timezone", "hora", "mundial", "utc", "gmt", "calculadora"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return WorldClockView(self, parent)


class WorldClockView(QWidget):
    def __init__(self, tool: WorldClockTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._refresh_clocks)

        self._build_ui()
        self._refresh_clocks()
        self._tick_timer.start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Relógio Mundial e Conversor de Fusos",
            "Acompanhe horários de trabalho de equipes globais e converta reuniões entre fusos com exatidão."
        ))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_clocks_tab(), "Relógios Globais ao Vivo")
        self.tabs.addTab(self._build_converter_tab(), "Conversor de Horário")
        root.addWidget(self.tabs, stretch=1)

    # 1. Aba Relógios
    def _build_clocks_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        self.table_clocks = QTableWidget()
        self.table_clocks.setColumnCount(5)
        self.table_clocks.setHorizontalHeaderLabels(["Cidade / Referência", "Região", "Horário Atual", "Data", "Offset UTC"])
        self.table_clocks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_clocks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_clocks.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_clocks.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_clocks.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        enable_sorting_on_table(self.table_clocks)

        layout.addWidget(self.table_clocks, stretch=1)
        return tab

    def _refresh_clocks(self) -> None:
        clocks = get_all_world_clocks()
        with batch_table_update(self.table_clocks):
            if self.table_clocks.rowCount() != len(clocks):
                self.table_clocks.setRowCount(len(clocks))

            for row, c in enumerate(clocks):
                # Cidade
                self.table_clocks.setItem(row, 0, SmartTableWidgetItem(c["city"], user_data=c))
                # Região
                self.table_clocks.setItem(row, 1, SmartTableWidgetItem(c["region"]))

                # Horário (em destaque)
                time_item = SmartTableWidgetItem(c["time_str"])
                time_item.setFont(QFont("Cascadia Mono", 11, QFont.Weight.Bold))
                if "Brasília" in c["city"]:
                    time_item.setForeground(QColor("#10B981"))
                self.table_clocks.setItem(row, 2, time_item)

                # Data
                self.table_clocks.setItem(row, 3, SmartTableWidgetItem(c["date_str"]))
                # Offset
                self.table_clocks.setItem(row, 4, SmartTableWidgetItem(f"{c['offset_str']} ({c['tz_abbr']})"))

    # 2. Aba Conversor
    def _build_converter_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        box = QGroupBox("Parâmetros de Conversão")
        grid = QGridLayout(box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Data e Horário de Origem:"), 0, 0)
        self.dt_source = QDateTimeEdit()
        self.dt_source.setCalendarPopup(True)
        self.dt_source.setDateTime(QDateTime.currentDateTime())
        self.dt_source.dateTimeChanged.connect(self._convert_timezone)
        grid.addWidget(self.dt_source, 0, 1)

        grid.addWidget(QLabel("Fuso de Origem:"), 1, 0)
        self.combo_tz_src = QComboBox()
        for city, tz_name, _ in POPULAR_TIMEZONES:
            self.combo_tz_src.addItem(f"{city} ({tz_name})", tz_name)
        self.combo_tz_src.currentIndexChanged.connect(self._convert_timezone)
        grid.addWidget(self.combo_tz_src, 1, 1)

        grid.addWidget(QLabel("Fuso de Destino:"), 2, 0)
        self.combo_tz_dst = QComboBox()
        for city, tz_name, _ in POPULAR_TIMEZONES:
            self.combo_tz_dst.addItem(f"{city} ({tz_name})", tz_name)
        # Seleciona UTC ou Nova York
        self.combo_tz_dst.setCurrentIndex(2)
        self.combo_tz_dst.currentIndexChanged.connect(self._convert_timezone)
        grid.addWidget(self.combo_tz_dst, 2, 1)

        btn_swap = QPushButton("Inverter Fusos")
        btn_swap.clicked.connect(self._swap_timezones)
        grid.addWidget(btn_swap, 2, 2)

        layout.addWidget(box)

        # Resultado
        res_frame = QFrame()
        res_frame.setProperty("class", "card")
        res_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 16px; }")
        res_lay = QVBoxLayout(res_frame)
        res_lay.setSpacing(8)

        res_lay.addWidget(QLabel("Horário Convertido no Destino:"))
        self.lbl_converted_time = QLabel("Calculando...")
        self.lbl_converted_time.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_converted_time.setStyleSheet("color: #10B981;")
        res_lay.addWidget(self.lbl_converted_time)

        self.lbl_tz_details = QLabel("")
        self.lbl_tz_details.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        res_lay.addWidget(self.lbl_tz_details)

        btn_copy = QPushButton("Copiar Horário Convertido")
        btn_copy.setProperty("class", "primary")
        btn_copy.setFixedWidth(180)
        btn_copy.clicked.connect(self._copy_converted)
        res_lay.addWidget(btn_copy)

        layout.addWidget(res_frame)
        layout.addStretch(1)

        self._convert_timezone()
        return tab

    def _swap_timezones(self) -> None:
        idx_s = self.combo_tz_src.currentIndex()
        idx_d = self.combo_tz_dst.currentIndex()
        self.combo_tz_src.blockSignals(True)
        self.combo_tz_dst.blockSignals(True)
        self.combo_tz_src.setCurrentIndex(idx_d)
        self.combo_tz_dst.setCurrentIndex(idx_s)
        self.combo_tz_src.blockSignals(False)
        self.combo_tz_dst.blockSignals(False)
        self._convert_timezone()

    def _convert_timezone(self) -> None:
        qdt = self.dt_source.dateTime()
        py_dt = datetime(
            qdt.date().year(), qdt.date().month(), qdt.date().day(),
            qdt.time().hour(), qdt.time().minute(), qdt.time().second()
        )

        src_tz = self.combo_tz_src.currentData() or "America/Sao_Paulo"
        dst_tz = self.combo_tz_dst.currentData() or "UTC"

        try:
            res = convert_time_between_zones(py_dt, src_tz, dst_tz)
            self.lbl_converted_time.setText(f"{res['target_str']} ({res['target_abbr']})")
            self.lbl_tz_details.setText(f"Origem: {res['source_str']} ({res['source_offset']})  ➔  Destino: {res['target_str']} ({res['target_offset']})")
        except Exception as exc:
            self.lbl_converted_time.setText(f"Erro: {exc}")

    def _copy_converted(self) -> None:
        txt = self.lbl_converted_time.text()
        if txt:
            QApplication.clipboard().setText(txt)
            show_toast(self, "Horário copiado para a área de transferência!")
