"""
Interface de usuário para a ferramenta Controle de Finanças Pessoais.
"""
import csv
from pathlib import Path
from typing import List

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.finance_tracker.logic import (
    DEFAULT_CATEGORIES,
    Transaction,
    calculate_balance_summary,
    parse_csv_bank_statement,
    parse_ofx_file,
)


@register
class FinanceTrackerTool(Tool):
    """Controle de finanças pessoais offline com suporte a extratos OFX/CSV e balanço."""

    id = "productivity.finance_tracker"
    name = "Controle de Finanças Pessoais"
    description = "Gestão financeira 100% offline com importação de extratos OFX/CSV, categorização e balanço mensal."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.transactions: List[Transaction] = []

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Controle de Finanças Pessoais")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Gerencie suas contas com privacidade total. Importe extratos OFX e planilhas CSV "
            "sem enviar dados bancários para a nuvem."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Cartões de Resumo (Cards)
        cards_layout = QHBoxLayout()

        # Saldo
        self.card_balance = QFrame()
        self.card_balance.setFrameShape(QFrame.Shape.StyledPanel)
        v_bal = QVBoxLayout(self.card_balance)
        v_bal.addWidget(QLabel("Saldo Geral"))
        self.lbl_balance = QLabel("R$ 0,00")
        self.lbl_balance.setStyleSheet("font-size: 20px; font-weight: bold; color: #4caf50;")
        v_bal.addWidget(self.lbl_balance)
        cards_layout.addWidget(self.card_balance)

        # Receitas
        self.card_income = QFrame()
        self.card_income.setFrameShape(QFrame.Shape.StyledPanel)
        v_inc = QVBoxLayout(self.card_income)
        v_inc.addWidget(QLabel("Total de Entradas"))
        self.lbl_income = QLabel("R$ 0,00")
        self.lbl_income.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196f3;")
        v_inc.addWidget(self.lbl_income)
        cards_layout.addWidget(self.card_income)

        # Despesas
        self.card_expense = QFrame()
        self.card_expense.setFrameShape(QFrame.Shape.StyledPanel)
        v_exp = QVBoxLayout(self.card_expense)
        v_exp.addWidget(QLabel("Total de Saídas"))
        self.lbl_expense = QLabel("R$ 0,00")
        self.lbl_expense.setStyleSheet("font-size: 18px; font-weight: bold; color: #f44336;")
        v_exp.addWidget(self.lbl_expense)
        cards_layout.addWidget(self.card_expense)

        layout.addLayout(cards_layout)

        # Barra de Ações
        actions_frame = QFrame()
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        btn_import = QPushButton("📥 Importar Extrato (OFX / CSV)...")
        btn_import.setStyleSheet("font-weight: bold;")
        btn_import.clicked.connect(self._import_statement)

        btn_add = QPushButton("+ Nova Transação Manual")
        btn_add.clicked.connect(self._add_transaction_dialog)

        btn_export = QPushButton("Exportar CSV...")
        btn_export.clicked.connect(self._export_csv)

        btn_clear = QPushButton("Limpar Todas")
        btn_clear.clicked.connect(self._clear_all)

        actions_layout.addWidget(btn_import)
        actions_layout.addWidget(btn_add)
        actions_layout.addWidget(btn_export)
        actions_layout.addStretch()
        actions_layout.addWidget(btn_clear)

        layout.addWidget(actions_frame)

        # Splitter: Tabela de Transações e Resumo de Categorias
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tabela de Transações
        w_table = QWidget()
        v_table = QVBoxLayout(w_table)
        v_table.setContentsMargins(0, 0, 0, 0)

        h_filt = QHBoxLayout()
        h_filt.addWidget(QLabel("Filtrar Categoria:"))
        self.combo_filter_cat = QComboBox()
        self.combo_filter_cat.addItem("Todas as Categorias", "")
        for c in DEFAULT_CATEGORIES:
            self.combo_filter_cat.addItem(c, c)
        self.combo_filter_cat.currentIndexChanged.connect(self._apply_filters)
        h_filt.addWidget(self.combo_filter_cat)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar descrição...")
        self.txt_search.textChanged.connect(self._apply_filters)
        h_filt.addWidget(self.txt_search, 1)

        v_table.addLayout(h_filt)

        self.table_tx = QTableWidget()
        self.table_tx.setColumnCount(5)
        self.table_tx.setHorizontalHeaderLabels(["Data", "Descrição", "Categoria", "Conta", "Valor"])
        self.table_tx.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        v_table.addWidget(self.table_tx)
        splitter.addWidget(w_table)

        # Tabela de Categorias
        w_cat = QWidget()
        v_cat = QVBoxLayout(w_cat)
        v_cat.setContentsMargins(0, 0, 0, 0)
        v_cat.addWidget(QLabel("Gastos por Categoria:"))

        self.table_cat = QTableWidget()
        self.table_cat.setColumnCount(3)
        self.table_cat.setHorizontalHeaderLabels(["Categoria", "Total (R$)", "%"])
        self.table_cat.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v_cat.addWidget(self.table_cat)
        splitter.addWidget(w_cat)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter, 1)

        self._refresh_ui()
        return widget

    def _import_statement(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Importar Extrato Bancário", "",
            "Extratos Bancários (*.ofx *.csv);;Arquivos OFX (*.ofx);;Arquivos CSV (*.csv)"
        )
        if not file_path:
            return

        p = Path(file_path)
        try:
            if p.suffix.lower() == ".ofx":
                new_txs = parse_ofx_file(p, account_name=p.stem)
            else:
                new_txs = parse_csv_bank_statement(p, account_name=p.stem)

            self.transactions.extend(new_txs)
            self._refresh_ui()
            QMessageBox.information(
                None, "Importação Concluída", f"{len(new_txs)} transações importadas com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(None, "Erro ao Importar", f"Falha ao ler extrato: {e}")

    def _add_transaction_dialog(self):
        dlg = QDialog()
        dlg.setWindowTitle("Nova Transação")
        dlg.resize(400, 260)
        v = QVBoxLayout(dlg)

        grid = QGridLayout()
        grid.addWidget(QLabel("Data:"), 0, 0)
        date_edit = QDateEdit(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd/MM/yyyy")
        grid.addWidget(date_edit, 0, 1)

        grid.addWidget(QLabel("Descrição:"), 1, 0)
        txt_desc = QLineEdit()
        grid.addWidget(txt_desc, 1, 1)

        grid.addWidget(QLabel("Valor (Positivo = Entrada, Negativo = Saída):"), 2, 0)
        spin_amt = QDoubleSpinBox()
        spin_amt.setRange(-10000000, 10000000)
        spin_amt.setValue(-50.0)
        spin_amt.setPrefix("R$ ")
        grid.addWidget(spin_amt, 2, 1)

        grid.addWidget(QLabel("Categoria:"), 3, 0)
        combo_cat = QComboBox()
        combo_cat.addItems(DEFAULT_CATEGORIES)
        grid.addWidget(combo_cat, 3, 1)

        grid.addWidget(QLabel("Conta:"), 4, 0)
        txt_acc = QLineEdit("Carteira")
        grid.addWidget(txt_acc, 4, 1)

        v.addLayout(grid)

        btns = QHBoxLayout()
        b_ok = QPushButton("Salvar")
        b_ok.clicked.connect(dlg.accept)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(dlg.reject)
        btns.addStretch()
        btns.addWidget(b_ok)
        btns.addWidget(b_cancel)
        v.addLayout(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            import uuid
            qdate = date_edit.date()
            date_iso = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"
            tx = Transaction(
                id=str(uuid.uuid4())[:8],
                date=date_iso,
                description=txt_desc.text().strip() or "Transação Manual",
                amount=spin_amt.value(),
                category=combo_cat.currentText(),
                account=txt_acc.text().strip() or "Padrão"
            )
            self.transactions.append(tx)
            self._refresh_ui()

    def _refresh_ui(self):
        # Atualiza resumo
        summary = calculate_balance_summary(self.transactions)
        bal = summary["balance"]
        bal_color = "#4caf50" if bal >= 0 else "#f44336"
        self.lbl_balance.setText(f"R$ {bal:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_balance.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {bal_color};")

        inc = summary["total_income"]
        self.lbl_income.setText(f"R$ {inc:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        exp = summary["total_expense"]
        self.lbl_expense.setText(f"R$ {exp:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # Atualiza tabela de categorias
        cat_map = summary["categories_breakdown"]
        sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)
        self.table_cat.setRowCount(len(sorted_cats))

        for row, (c_name, c_val) in enumerate(sorted_cats):
            pct = (c_val / exp * 100) if exp > 0 else 0.0
            val_fmt = f"R$ {c_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            self.table_cat.setItem(row, 0, QTableWidgetItem(c_name))
            self.table_cat.setItem(row, 1, QTableWidgetItem(val_fmt))
            self.table_cat.setItem(row, 2, QTableWidgetItem(f"{pct:.1f}%"))

        self._apply_filters()

    def _apply_filters(self):
        cat_filter = self.combo_filter_cat.currentData()
        search_txt = self.txt_search.text().lower().strip()

        filtered = []
        for t in self.transactions:
            if cat_filter and t.category != cat_filter:
                continue
            if search_txt and search_txt not in t.description.lower():
                continue
            filtered.append(t)

        # Ordena por data decrescente
        filtered.sort(key=lambda x: x.date, reverse=True)

        self.table_tx.setRowCount(len(filtered))
        for row, tx in enumerate(filtered):
            self.table_tx.setItem(row, 0, QTableWidgetItem(tx.date))
            self.table_tx.setItem(row, 1, QTableWidgetItem(tx.description))
            self.table_tx.setItem(row, 2, QTableWidgetItem(tx.category))
            self.table_tx.setItem(row, 3, QTableWidgetItem(tx.account))

            amt_fmt = f"R$ {tx.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            it_amt = QTableWidgetItem(amt_fmt)
            if tx.amount >= 0:
                it_amt.setForeground(QColor(76, 175, 80))
            else:
                it_amt.setForeground(QColor(244, 67, 54))
            self.table_tx.setItem(row, 4, it_amt)

    def _export_csv(self):
        if not self.transactions:
            QMessageBox.information(None, "Aviso", "Não há transações para exportar.")
            return

        dest, _ = QFileDialog.getSaveFileName(
            None, "Exportar Extrato CSV", "transacoes_financeiras.csv", "Planilha CSV (*.csv)"
        )
        if dest:
            try:
                with open(dest, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow(["ID", "Data", "Descricao", "Categoria", "Conta", "Valor"])
                    for t in self.transactions:
                        writer.writerow([t.id, t.date, t.description, t.category, t.account, f"{t.amount:.2f}"])
                QMessageBox.information(None, "Sucesso", f"Exportado com sucesso em:\n{dest}")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar: {e}")

    def _clear_all(self):
        if not self.transactions:
            return
        if QMessageBox.question(None, "Confirmar", "Deseja limpar todas as transações?") == QMessageBox.StandardButton.Yes:
            self.transactions.clear()
            self._refresh_ui()
