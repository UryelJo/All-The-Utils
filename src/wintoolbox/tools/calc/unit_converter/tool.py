"""
Interface gráfica do Conversor de Unidades de Medida.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.unit_converter.logic import (
    convert_units, get_all_conversions_in_category, get_categories,
    get_units_for_category
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

_log = get_logger("calc.unit_converter.ui")


@register
class UnitConverterTool(Tool):
    id = "calc.unit_converter"
    name = "Conversor de Unidades"
    category = "Calculadoras"
    description = "Conversor instantâneo de medidas: comprimento (m, km, milhas, pés), peso/massa (kg, lb, oz), temperatura (°C, °F, K), volume (L, gal), dados digitais (MB, GB, TB) e velocidade."
    keywords = ["unidades", "conversor", "medidas", "metro", "peso", "temperatura", "bytes", "volume", "calculadora"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return UnitConverterView(self, parent)


class UnitConverterView(QWidget):
    def __init__(self, tool: UnitConverterTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._updating = False

        self._build_ui()
        self._populate_categories()
        self._calculate()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Conversor de Unidades de Medida",
            "Conversões matemáticas de alta precisão entre grandezas físicas, digitais e térmicas."
        ))

        # 1. Seletor de Categoria
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Categoria de Medida:"))
        self.combo_category = QComboBox()
        self.combo_category.currentIndexChanged.connect(self._on_category_changed)
        top_row.addWidget(self.combo_category, stretch=1)
        root.addLayout(top_row)

        # 2. Card Principal de Conversão
        conv_box = QGroupBox("Conversão Direta")
        grid = QGridLayout(conv_box)
        grid.setSpacing(12)

        # Origem
        grid.addWidget(QLabel("Valor de Entrada:"), 0, 0)
        self.spin_value = QDoubleSpinBox()
        self.spin_value.setRange(-1e15, 1e15)
        self.spin_value.setDecimals(4)
        self.spin_value.setValue(1.0)
        self.spin_value.setFont(QFont("Cascadia Mono", 11))
        self.spin_value.valueChanged.connect(self._calculate)
        grid.addWidget(self.spin_value, 0, 1)

        self.combo_from = QComboBox()
        self.combo_from.currentIndexChanged.connect(self._calculate)
        grid.addWidget(self.combo_from, 0, 2)

        # Botão Inverter
        btn_swap = QPushButton("Inverter Unidades")
        btn_swap.clicked.connect(self._swap_units)
        grid.addWidget(btn_swap, 0, 3)

        # Destino
        grid.addWidget(QLabel("Resultado Convertido:"), 1, 0)
        self.edit_result = QLineEdit()
        self.edit_result.setReadOnly(True)
        self.edit_result.setFont(QFont("Cascadia Mono", 12, QFont.Weight.Bold))
        self.edit_result.setStyleSheet("color: #10B981; padding: 4px;")
        grid.addWidget(self.edit_result, 1, 1)

        self.combo_to = QComboBox()
        self.combo_to.currentIndexChanged.connect(self._calculate)
        grid.addWidget(self.combo_to, 1, 2)

        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.setProperty("class", "primary")
        btn_copy.clicked.connect(self._copy_result)
        grid.addWidget(btn_copy, 1, 3)

        root.addWidget(conv_box)

        # 3. Tabela de Equivalências na Mesma Categoria
        table_box = QGroupBox("Equivalências Completas na Categoria")
        table_layout = QVBoxLayout(table_box)
        table_layout.setSpacing(6)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Unidade de Destino", "Valor Equivalente", "Ação"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 70)
        enable_sorting_on_table(self.table)
        table_layout.addWidget(self.table)

        root.addWidget(table_box, stretch=1)

    def _populate_categories(self) -> None:
        self.combo_category.blockSignals(True)
        self.combo_category.clear()
        self.combo_category.addItems(get_categories())
        self.combo_category.blockSignals(False)
        self._on_category_changed()

    def _on_category_changed(self) -> None:
        cat = self.combo_category.currentText()
        units = get_units_for_category(cat)

        self.combo_from.blockSignals(True)
        self.combo_to.blockSignals(True)

        self.combo_from.clear()
        self.combo_to.clear()
        self.combo_from.addItems(units)
        self.combo_to.addItems(units)

        if len(units) > 1:
            self.combo_to.setCurrentIndex(1)

        self.combo_from.blockSignals(False)
        self.combo_to.blockSignals(False)
        self._calculate()

    def _swap_units(self) -> None:
        idx_from = self.combo_from.currentIndex()
        idx_to = self.combo_to.currentIndex()
        self.combo_from.blockSignals(True)
        self.combo_to.blockSignals(True)
        self.combo_from.setCurrentIndex(idx_to)
        self.combo_to.setCurrentIndex(idx_from)
        self.combo_from.blockSignals(False)
        self.combo_to.blockSignals(False)
        self._calculate()

    def _calculate(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            val = self.spin_value.value()
            cat = self.combo_category.currentText()
            u_from = self.combo_from.currentText()
            u_to = self.combo_to.currentText()

            if not u_from or not u_to:
                return

            res = convert_units(val, cat, u_from, u_to)
            # Formatação limpa de ponto flutuante
            if abs(res) >= 1e6 or (0 < abs(res) < 1e-4):
                res_str = f"{res:.6e}"
            else:
                res_str = f"{res:.6f}".rstrip("0").rstrip(".")

            self.edit_result.setText(res_str)

            # Atualiza Tabela de Equivalências
            all_convs = get_all_conversions_in_category(val, cat, u_from)
            with batch_table_update(self.table):
                self.table.setRowCount(len(all_convs))
                for row, (uname, uval) in enumerate(all_convs):
                    if abs(uval) >= 1e6 or (0 < abs(uval) < 1e-4):
                        formatted_val = f"{uval:.6e}"
                    else:
                        formatted_val = f"{uval:.6f}".rstrip("0").rstrip(".")

                    self.table.setItem(row, 0, SmartTableWidgetItem(uname, user_data=uname))
                    val_item = SmartTableWidgetItem(formatted_val, sort_value=uval)
                    val_item.setFont(QFont("Cascadia Mono", 9))
                    self.table.setItem(row, 1, val_item)

                    btn_c = QPushButton("Copiar")
                    btn_c.setStyleSheet("font-size: 10px; padding: 2px;")
                    btn_c.clicked.connect(lambda checked=False, text=formatted_val: self._copy_specific_val(text))
                    self.table.setCellWidget(row, 2, btn_c)

        except Exception as exc:
            self.edit_result.setText(f"Erro: {exc}")
        finally:
            self._updating = False

    def _copy_result(self) -> None:
        txt = self.edit_result.text()
        if txt:
            QApplication.clipboard().setText(txt)
            show_toast(self, "Valor copiado para a área de transferência!")

    def _copy_specific_val(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        show_toast(self, f"Valor '{text}' copiado!", duration_ms=1500)
