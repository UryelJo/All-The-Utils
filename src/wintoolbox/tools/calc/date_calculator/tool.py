"""
Interface gráfica da Calculadora de Datas, Dias Úteis e Prazos.
"""
from datetime import date
from typing import Optional
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDateEdit, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.date_calculator.logic import (
    add_business_days, add_calendar_interval, diff_dates, get_detailed_holidays_for_year
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

_log = get_logger("calc.date_calculator.ui")


@register
class DateCalculatorTool(Tool):
    id = "calc.date_calculator"
    name = "Calculadora de Datas"
    category = "Calculadoras"
    description = "Calcula o intervalo exato entre datas (anos, meses, dias), soma ou subtrai prazos e conta dias úteis desconsiderando fins de semana e feriados nacionais do Brasil."
    keywords = ["datas", "prazo", "dias uteis", "calendario", "feriados", "calculadora", "tempo"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DateCalculatorView(self, parent)


class DateCalculatorView(QWidget):
    def __init__(self, tool: DateCalculatorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Calculadora de Datas e Prazos",
            "Cálculo exato de intervalos, contagem de dias úteis e projeção de prazos legais e comerciais."
        ))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_diff_tab(), "Diferença Entre Datas")
        self.tabs.addTab(self._build_business_days_tab(), "Calcular Dias Úteis")
        self.tabs.addTab(self._build_interval_tab(), "Somar / Subtrair Períodos")
        self.tabs.addTab(self._build_holidays_tab(), "Feriados do Ano")
        root.addWidget(self.tabs, stretch=1)

    # 1. Aba Diferença
    def _build_diff_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        input_box = QGroupBox("Período de Análise")
        grid = QGridLayout(input_box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Data Inicial:"), 0, 0)
        self.diff_date_start = QDateEdit()
        self.diff_date_start.setCalendarPopup(True)
        self.diff_date_start.setDate(QDate.currentDate())
        self.diff_date_start.dateChanged.connect(self._calculate_diff)
        grid.addWidget(self.diff_date_start, 0, 1)

        grid.addWidget(QLabel("Data Final:"), 0, 2)
        self.diff_date_end = QDateEdit()
        self.diff_date_end.setCalendarPopup(True)
        self.diff_date_end.setDate(QDate.currentDate().addDays(30))
        self.diff_date_end.dateChanged.connect(self._calculate_diff)
        grid.addWidget(self.diff_date_end, 0, 3)

        self.chk_holidays_diff = QCheckBox("Descontar Feriados Nacionais Brasileiros")
        self.chk_holidays_diff.setChecked(True)
        self.chk_holidays_diff.toggled.connect(self._calculate_diff)
        grid.addWidget(self.chk_holidays_diff, 1, 0, 1, 4)

        layout.addWidget(input_box)

        # Resultados
        res_box = QGroupBox("Detalhamento do Intervalo")
        res_layout = QVBoxLayout(res_box)
        res_layout.setSpacing(8)

        self.lbl_res_days = QLabel("Total: 0 dias corridos")
        self.lbl_res_days.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_res_days.setStyleSheet("color: #60A5FA;")
        res_layout.addWidget(self.lbl_res_days)

        self.lbl_res_details = QLabel("Calculando...")
        self.lbl_res_details.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.8);")
        res_layout.addWidget(self.lbl_res_details)

        res_layout.addWidget(QLabel("Feriados que caem no período:"))
        self.list_holidays = QListWidget()
        res_layout.addWidget(self.list_holidays, stretch=1)

        layout.addWidget(res_box, stretch=1)

        self._calculate_diff()
        return tab

    def _calculate_diff(self) -> None:
        qd1 = self.diff_date_start.date()
        qd2 = self.diff_date_end.date()
        d1 = date(qd1.year(), qd1.month(), qd1.day())
        d2 = date(qd2.year(), qd2.month(), qd2.day())

        res = diff_dates(d1, d2, consider_holidays=self.chk_holidays_diff.isChecked())

        tot = res["total_days"]
        b_days = res["business_days"]
        w_days = res["weekend_days"]
        h_days = res["holidays_count"]
        weeks = res["weeks"]
        rem = res["remaining_days"]

        self.lbl_res_days.setText(f"{tot} dias corridos ({weeks} semanas e {rem} dias)")
        self.lbl_res_details.setText(
            f"• Dias Úteis de Trabalho: {b_days} dias\n"
            f"• Finais de Semana: {w_days} dias (Sábados e Domingos)\n"
            f"• Feriados no Período: {h_days} feriado(s)\n"
            f"• Total em Horas: {res['total_hours']:,} horas".replace(",", ".")
        )

        self.list_holidays.clear()
        if res["holidays_list"]:
            for h in res["holidays_list"]:
                # Formata data
                dt_obj = date.fromisoformat(h["date"])
                item = QListWidgetItem(f"• {dt_obj.strftime('%d/%m/%Y')} — {h['name']}")
                self.list_holidays.addItem(item)
        else:
            self.list_holidays.addItem(QListWidgetItem("Nenhum feriado nacional neste período."))

    # 2. Aba Dias Úteis
    def _build_business_days_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        box = QGroupBox("Adicionar ou Subtrair Dias Úteis (Prazos)")
        grid = QGridLayout(box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Data Base / Inicial:"), 0, 0)
        self.biz_date_start = QDateEdit()
        self.biz_date_start.setCalendarPopup(True)
        self.biz_date_start.setDate(QDate.currentDate())
        self.biz_date_start.dateChanged.connect(self._calculate_biz_days)
        grid.addWidget(self.biz_date_start, 0, 1)

        grid.addWidget(QLabel("Dias Úteis a Somar:"), 1, 0)
        self.spin_biz_days = QSpinBox()
        self.spin_biz_days.setRange(-5000, 5000)
        self.spin_biz_days.setValue(15)
        self.spin_biz_days.valueChanged.connect(self._calculate_biz_days)
        grid.addWidget(self.spin_biz_days, 1, 1)

        self.chk_holidays_biz = QCheckBox("Descontar Feriados Nacionais Brasileiros")
        self.chk_holidays_biz.setChecked(True)
        self.chk_holidays_biz.toggled.connect(self._calculate_biz_days)
        grid.addWidget(self.chk_holidays_biz, 2, 0, 1, 2)

        layout.addWidget(box)

        # Resultado
        res_frame = QFrame()
        res_frame.setProperty("class", "card")
        res_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 16px; }")
        res_lay = QVBoxLayout(res_frame)
        res_lay.setSpacing(6)

        res_lay.addWidget(QLabel("Data Final do Prazo Calculada:"))
        self.lbl_biz_result = QLabel("Carregando...")
        self.lbl_biz_result.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_biz_result.setStyleSheet("color: #10B981;")
        res_lay.addWidget(self.lbl_biz_result)

        layout.addWidget(res_frame)
        layout.addStretch(1)

        self._calculate_biz_days()
        return tab

    def _calculate_biz_days(self) -> None:
        qd = self.biz_date_start.date()
        base = date(qd.year(), qd.month(), qd.day())
        days = self.spin_biz_days.value()
        hols = self.chk_holidays_biz.isChecked()

        res_date = add_business_days(base, days, consider_holidays=hols)

        dow_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        dow_str = dow_pt[res_date.weekday()]

        self.lbl_biz_result.setText(f"{res_date.strftime('%d/%m/%Y')} ({dow_str})")

    # 3. Aba Intervalo Calendário
    def _build_interval_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        box = QGroupBox("Somar Anos, Meses e Dias Corridos")
        grid = QGridLayout(box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Data Base:"), 0, 0)
        self.cal_date_start = QDateEdit()
        self.cal_date_start.setCalendarPopup(True)
        self.cal_date_start.setDate(QDate.currentDate())
        self.cal_date_start.dateChanged.connect(self._calculate_interval)
        grid.addWidget(self.cal_date_start, 0, 1, 1, 3)

        grid.addWidget(QLabel("Anos:"), 1, 0)
        self.spin_years = QSpinBox()
        self.spin_years.setRange(-100, 100)
        self.spin_years.valueChanged.connect(self._calculate_interval)
        grid.addWidget(self.spin_years, 1, 1)

        grid.addWidget(QLabel("Meses:"), 1, 2)
        self.spin_months = QSpinBox()
        self.spin_months.setRange(-500, 500)
        self.spin_months.setValue(3)
        self.spin_months.valueChanged.connect(self._calculate_interval)
        grid.addWidget(self.spin_months, 1, 3)

        grid.addWidget(QLabel("Dias:"), 2, 0)
        self.spin_days = QSpinBox()
        self.spin_days.setRange(-5000, 5000)
        self.spin_days.valueChanged.connect(self._calculate_interval)
        grid.addWidget(self.spin_days, 2, 1)

        layout.addWidget(box)

        # Resultado
        res_frame = QFrame()
        res_frame.setProperty("class", "card")
        res_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 16px; }")
        res_lay = QVBoxLayout(res_frame)
        res_lay.setSpacing(6)

        res_lay.addWidget(QLabel("Data Resultante Calculada:"))
        self.lbl_cal_result = QLabel("Carregando...")
        self.lbl_cal_result.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_cal_result.setStyleSheet("color: #60A5FA;")
        res_lay.addWidget(self.lbl_cal_result)

        layout.addWidget(res_frame)
        layout.addStretch(1)

        self._calculate_interval()
        return tab

    def _calculate_interval(self) -> None:
        qd = self.cal_date_start.date()
        base = date(qd.year(), qd.month(), qd.day())
        y = self.spin_years.value()
        m = self.spin_months.value()
        d = self.spin_days.value()

        res_date = add_calendar_interval(base, years=y, months=m, days=d)

        dow_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        dow_str = dow_pt[res_date.weekday()]

        self.lbl_cal_result.setText(f"{res_date.strftime('%d/%m/%Y')} ({dow_str})")

    # 4. Aba Feriados Nacionais do Ano
    def _build_holidays_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Ano de Referência:"))

        self.spin_holidays_year = QSpinBox()
        self.spin_holidays_year.setRange(1900, 2199)
        self.spin_holidays_year.setValue(QDate.currentDate().year())
        self.spin_holidays_year.setFixedWidth(90)
        self.spin_holidays_year.valueChanged.connect(self._refresh_holidays_table)
        header_row.addWidget(self.spin_holidays_year)

        btn_copy = QPushButton("Copiar Feriados")
        btn_copy.clicked.connect(self._copy_holidays_to_clipboard)
        header_row.addWidget(btn_copy)

        header_row.addStretch(1)
        layout.addLayout(header_row)

        self.table_holidays = QTableWidget(0, 4)
        self.table_holidays.setHorizontalHeaderLabels(["Data", "Dia da Semana", "Feriado Nacional", "Classificação"])
        self.table_holidays.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_holidays.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_holidays.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_holidays.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_holidays.verticalHeader().setVisible(False)
        self.table_holidays.setAlternatingRowColors(True)
        enable_sorting_on_table(self.table_holidays)
        layout.addWidget(self.table_holidays, stretch=1)

        self.lbl_holidays_summary = QLabel()
        self.lbl_holidays_summary.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        layout.addWidget(self.lbl_holidays_summary)

        self._refresh_holidays_table()
        return tab

    def _refresh_holidays_table(self) -> None:
        year = self.spin_holidays_year.value()
        hols = get_detailed_holidays_for_year(year)

        with batch_table_update(self.table_holidays):
            self.table_holidays.setRowCount(len(hols))
            weekend_count = 0

            for row, h in enumerate(hols):
                it_date = SmartTableWidgetItem(h["formatted_date"], sort_value=h["date"], user_data=h)
                dow_text = f"{h['day_of_week']} (Fim de semana)" if h["is_weekend"] else h["day_of_week"]
                if h["is_weekend"]:
                    weekend_count += 1
                it_dow = SmartTableWidgetItem(dow_text)
                it_name = SmartTableWidgetItem(h["name"])
                it_type = SmartTableWidgetItem(h["type"])

                self.table_holidays.setItem(row, 0, it_date)
                self.table_holidays.setItem(row, 1, it_dow)
                self.table_holidays.setItem(row, 2, it_name)
                self.table_holidays.setItem(row, 3, it_type)

        biz_hols = len(hols) - weekend_count
        self.lbl_holidays_summary.setText(
            f"Total de {len(hols)} feriados nacionais em {year}: {biz_hols} caem em dias úteis e {weekend_count} em fins de semana."
        )

    def _copy_holidays_to_clipboard(self) -> None:
        year = self.spin_holidays_year.value()
        hols = get_detailed_holidays_for_year(year)
        lines = [f"Feriados Nacionais - {year}:"]
        for h in hols:
            lines.append(f"• {h['formatted_date']} ({h['day_of_week']}): {h['name']} [{h['type']}]")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        show_toast(self, "Lista de feriados copiada para a área de transferência!")
