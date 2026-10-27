"""
Interface de usuário para a Calculadora de Divisão de Contas e Rateio de Despesas.
"""
from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.split_bill.logic import (
    calculate_itemized_split,
    calculate_quick_split,
)


def fmt_reais(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register
class SplitBillTool(Tool):
    """Calculadora de divisão de contas de restaurante e rateio de despesas com gorjeta e itens individuais."""

    id = "calc.split_bill"
    name = "Calculadora de Divisão de Contas (Restaurante & Eventos)"
    description = "Divida contas de restaurante igualitariamente ou por consumo individualizado com taxa de serviço e couvert."
    category = "Calculadoras"

    def __init__(self):
        super().__init__()
        self.participants: List[str] = ["Carlos", "Ana", "João", "Marina"]
        self.items: List[Tuple[str, float, List[str]]] = [
            ("Pizza Grande Calabresa", 65.0, ["Carlos", "Ana", "João", "Marina"]),
            ("Porção de Batata Frita", 35.0, ["Carlos", "João"]),
            ("Refrigerante Refil (x2)", 24.0, ["Ana", "Marina"]),
            ("Cerveja Artesanal (x3)", 48.0, ["Carlos", "João"]),
        ]

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Calculadora de Divisão de Contas & Rateio Justo")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Divida despesas de refeições e viagens com justiça: divisão simples ou discriminação de quem consumiu o quê."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_quick_tab(), "Divisão Rápida (Igualitária)")
        tabs.addTab(self._build_itemized_tab(), "Divisão Individualizada (Item por Item)")

        return widget

    # -------------------------------------------------------------
    # ABA DIVISÃO RÁPIDA
    # -------------------------------------------------------------
    def _build_quick_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_quick_sub = QDoubleSpinBox()
        self.spn_quick_sub.setRange(0.0, 100000.0)
        self.spn_quick_sub.setPrefix("R$ ")
        self.spn_quick_sub.setValue(250.0)
        self.spn_quick_sub.valueChanged.connect(self._recalc_quick)
        f_layout.addRow("Subtotal dos Itens:", self.spn_quick_sub)

        self.spn_quick_people = QSpinBox()
        self.spn_quick_people.setRange(1, 100)
        self.spn_quick_people.setValue(4)
        self.spn_quick_people.setSuffix(" pessoas")
        self.spn_quick_people.valueChanged.connect(self._recalc_quick)
        f_layout.addRow("Número de Pessoas:", self.spn_quick_people)

        self.spn_quick_tax = QDoubleSpinBox()
        self.spn_quick_tax.setRange(0.0, 30.0)
        self.spn_quick_tax.setValue(10.0)
        self.spn_quick_tax.setSuffix(" %")
        self.spn_quick_tax.valueChanged.connect(self._recalc_quick)
        f_layout.addRow("Taxa de Serviço (Gorjeta):", self.spn_quick_tax)

        self.spn_quick_couvert = QDoubleSpinBox()
        self.spn_quick_couvert.setRange(0.0, 200.0)
        self.spn_quick_couvert.setPrefix("R$ ")
        self.spn_quick_couvert.setValue(10.0)
        self.spn_quick_couvert.valueChanged.connect(self._recalc_quick)
        f_layout.addRow("Couvert Artístico (por pessoa):", self.spn_quick_couvert)

        self.spn_quick_desc = QDoubleSpinBox()
        self.spn_quick_desc.setRange(0.0, 10000.0)
        self.spn_quick_desc.setPrefix("R$ ")
        self.spn_quick_desc.setValue(0.0)
        self.spn_quick_desc.valueChanged.connect(self._recalc_quick)
        f_layout.addRow("Desconto / Cupom:", self.spn_quick_desc)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_p = QFrame()
        card_p.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_p = QVBoxLayout(card_p)
        v_p.addWidget(QLabel("VALOR POR PESSOA:"))
        self.lbl_quick_per_person = QLabel("R$ 0,00")
        self.lbl_quick_per_person.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_p.addWidget(self.lbl_quick_per_person)
        v_res.addWidget(card_p)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Total Geral da Conta:"), 0, 0)
        self.lbl_quick_total = QLabel("R$ 0,00")
        self.lbl_quick_total.setStyleSheet("font-size: 16px; font-weight: bold;")
        grid.addWidget(self.lbl_quick_total, 0, 1)

        grid.addWidget(QLabel("Taxa de Serviço:"), 1, 0)
        self.lbl_quick_tax_val = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_quick_tax_val, 1, 1)

        grid.addWidget(QLabel("Total de Couvert:"), 2, 0)
        self.lbl_quick_couvert_val = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_quick_couvert_val, 2, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_quick()
        return page

    def _recalc_quick(self) -> None:
        sub = self.spn_quick_sub.value()
        p = self.spn_quick_people.value()
        tax = self.spn_quick_tax.value()
        couvert = self.spn_quick_couvert.value()
        desc = self.spn_quick_desc.value()

        res = calculate_quick_split(sub, p, tax, couvert, desc)
        self.lbl_quick_per_person.setText(fmt_reais(res["valor_por_pessoa"]))
        self.lbl_quick_total.setText(fmt_reais(res["total_geral"]))
        self.lbl_quick_tax_val.setText(fmt_reais(res["taxa_servico"]))
        self.lbl_quick_couvert_val.setText(fmt_reais(res["total_couvert"]))

    # -------------------------------------------------------------
    # ABA DIVISÃO INDIVIDUALIZADA
    # -------------------------------------------------------------
    def _build_itemized_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        top_ctrl = QHBoxLayout()
        top_ctrl.addWidget(QLabel("<b>Pessoas na Mesa:</b>"))
        self.txt_participants = QLineEdit(", ".join(self.participants))
        self.txt_participants.textChanged.connect(self._on_participants_changed)
        top_ctrl.addWidget(self.txt_participants, 2)

        top_ctrl.addWidget(QLabel("Taxa de Serviço:"))
        self.spn_item_tax = QDoubleSpinBox()
        self.spn_item_tax.setValue(10.0)
        self.spn_item_tax.setSuffix(" %")
        self.spn_item_tax.valueChanged.connect(self._recalc_itemized)
        top_ctrl.addWidget(self.spn_item_tax)

        top_ctrl.addWidget(QLabel("Couvert / pessoa:"))
        self.spn_item_couvert = QDoubleSpinBox()
        self.spn_item_couvert.setPrefix("R$ ")
        self.spn_item_couvert.setValue(0.0)
        self.spn_item_couvert.valueChanged.connect(self._recalc_itemized)
        top_ctrl.addWidget(self.spn_item_couvert)

        layout.addLayout(top_ctrl)

        # Divisão em duas tabelas (Itens consumidos e Rateio por pessoa)
        tables_box = QHBoxLayout()
        tables_box.setSpacing(10)

        # Tabela de Itens
        v_items = QVBoxLayout()
        v_items.addWidget(QLabel("<b>Itens Pedidos na Mesa:</b>"))
        self.tbl_items = QTableWidget(0, 3)
        self.tbl_items.setHorizontalHeaderLabels(["Item / Descrição", "Valor (R$)", "Consumidores"])
        self.tbl_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_items.setColumnWidth(1, 90)
        self.tbl_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_items.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_items.addWidget(self.tbl_items, 1)

        # Botões de item
        btn_item_box = QHBoxLayout()
        btn_add_item = QPushButton("+ Adicionar Item")
        btn_add_item.clicked.connect(self._on_add_item)
        btn_del_item = QPushButton("Excluir Item")
        btn_del_item.clicked.connect(self._on_delete_item)
        btn_item_box.addWidget(btn_add_item)
        btn_item_box.addWidget(btn_del_item)
        v_items.addLayout(btn_item_box)
        tables_box.addLayout(v_items, 1)

        # Tabela de Resultado Individual
        v_res = QVBoxLayout()
        v_res.addWidget(QLabel("<b>Extrato Final por Pessoa:</b>"))
        self.tbl_results = QTableWidget(0, 4)
        self.tbl_results.setHorizontalHeaderLabels(["Nome", "Subtotal", "Taxa + Couvert", "Total a Pagar"])
        self.tbl_results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_res.addWidget(self.tbl_results, 1)

        self.lbl_itemized_total = QLabel("Total da Conta: R$ 0,00")
        self.lbl_itemized_total.setStyleSheet("font-size: 15px; font-weight: bold; color: #16a34a;")
        v_res.addWidget(self.lbl_itemized_total)

        tables_box.addLayout(v_res, 1)
        layout.addLayout(tables_box, 1)

        self._refresh_items_table()
        self._recalc_itemized()
        return page

    def _on_participants_changed(self) -> None:
        raw = self.txt_participants.text()
        self.participants = [p.strip() for p in raw.split(",") if p.strip()]
        self._recalc_itemized()

    def _refresh_items_table(self) -> None:
        self.tbl_items.setRowCount(0)
        for desc, val, consumers in self.items:
            r = self.tbl_items.rowCount()
            self.tbl_items.insertRow(r)
            self.tbl_items.setItem(r, 0, QTableWidgetItem(desc))
            self.tbl_items.setItem(r, 1, QTableWidgetItem(fmt_reais(val)))
            self.tbl_items.setItem(r, 2, QTableWidgetItem(", ".join(consumers) if consumers else "Todos"))

    def _on_add_item(self) -> None:
        dlg = QDialog()
        dlg.setWindowTitle("Adicionar Item à Conta")
        dlg.resize(340, 200)
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        txt_d = QLineEdit()
        form.addRow("Descrição:", txt_d)
        spn_v = QDoubleSpinBox()
        spn_v.setRange(0.1, 10000.0)
        spn_v.setValue(25.0)
        spn_v.setPrefix("R$ ")
        form.addRow("Valor:", spn_v)

        txt_c = QLineEdit(", ".join(self.participants))
        form.addRow("Quem consumiu:", txt_c)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Adicionar")
        btn_ok.clicked.connect(dlg.accept)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        if dlg.exec():
            d = txt_d.text().strip() or "Item"
            v = spn_v.value()
            c = [p.strip() for p in txt_c.text().split(",") if p.strip()]
            self.items.append((d, v, c))
            self._refresh_items_table()
            self._recalc_itemized()

    def _on_delete_item(self) -> None:
        row = self.tbl_items.currentRow()
        if 0 <= row < len(self.items):
            del self.items[row]
            self._refresh_items_table()
            self._recalc_itemized()

    def _recalc_itemized(self) -> None:
        tax = self.spn_item_tax.value()
        couvert = self.spn_item_couvert.value()

        res = calculate_itemized_split(self.participants, self.items, tax, couvert)
        if not res:
            self.tbl_results.setRowCount(0)
            return

        bk = res["participants_breakdown"]
        self.tbl_results.setRowCount(len(bk))

        for r, (p, info) in enumerate(bk.items()):
            self.tbl_results.setItem(r, 0, QTableWidgetItem(p))
            self.tbl_results.setItem(r, 1, QTableWidgetItem(fmt_reais(info["consumo_subtotal"])))
            tax_couvert = info["taxa_servico"] + info["couvert"]
            self.tbl_results.setItem(r, 2, QTableWidgetItem(fmt_reais(tax_couvert)))

            it_tot = QTableWidgetItem(fmt_reais(info["total_a_pagar"]))
            it_tot.setForeground(Qt.GlobalColor.darkGreen)
            self.tbl_results.setItem(r, 3, it_tot)

        self.lbl_itemized_total.setText(f"Total Geral da Conta: {fmt_reais(res['total_geral'])}")
