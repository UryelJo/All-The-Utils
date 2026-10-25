
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.public_apis.logic import (
    fetch_banks, fetch_brasilapi_holidays, fetch_cep_info, fetch_cnpj_info,
    fetch_currency_quotes, fetch_ddd_info, fetch_fipe_info
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

__all__ = ["PublicApisTool", "PublicApisView", "fetch_cep_info", "fetch_cnpj_info", "fetch_currency_quotes"]


@register
class PublicApisTool(Tool):
    id = "network.public_apis"
    name = "Consultas Públicas e BrasilAPI"
    category = "Rede e Internet"
    description = "Consulta de CEP, CNPJ, DDD, Bancos autorizados, Feriados Nacionais, Tabela FIPE e Cotações em tempo real"
    keywords = [
        "cep", "cnpj", "cotacao", "dolar", "euro", "bitcoin", "moedas",
        "brasilapi", "viacep", "empresa", "endereco", "ddd", "bancos",
        "feriados", "fipe", "tabela fipe", "veiculos"
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PublicApisView(self, parent)


class PublicApisView(QWidget):
    def __init__(self, tool: PublicApisTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._quotes_cache: Dict[str, Dict[str, Any]] = {}
        self._all_banks_cache: List[Dict[str, Any]] = []

        self._build_ui()


    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        root_layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        tabs = QTabWidget()

        tabs.addTab(self._build_cep_tab(), "CEP")
        tabs.addTab(self._build_cnpj_tab(), "CNPJ")
        tabs.addTab(self._build_ddd_tab(), "DDD")
        tabs.addTab(self._build_banks_tab(), "Bancos")
        tabs.addTab(self._build_holidays_tab(), "Feriados")
        tabs.addTab(self._build_fipe_tab(), "Tabela FIPE")
        tabs.addTab(self._build_quotes_tab(), "Cotações")

        root_layout.addWidget(tabs, stretch=1)

    # 1. ABA CEP
    def _build_cep_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("CEP (8 dígitos):"))
        self.txt_cep = QLineEdit("01001-000")
        self.txt_cep.setFixedWidth(130)
        self.txt_cep.returnPressed.connect(self._consult_cep)
        row_in.addWidget(self.txt_cep)

        btn_consult = QPushButton("Consultar CEP")
        btn_consult.setProperty("class", "primary")
        btn_consult.clicked.connect(self._consult_cep)
        row_in.addWidget(btn_consult)

        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.clicked.connect(lambda: self._copy_table_content(self.table_cep))
        row_in.addWidget(btn_copy)

        row_in.addStretch()
        layout.addLayout(row_in)

        self.table_cep = QTableWidget(0, 2)
        self.table_cep.setHorizontalHeaderLabels(["Campo", "Informação"])
        self.table_cep.horizontalHeader().setStretchLastSection(True)
        self.table_cep.verticalHeader().setVisible(False)
        self.table_cep.setAlternatingRowColors(True)
        layout.addWidget(self.table_cep, stretch=1)

        return tab

    def _consult_cep(self) -> None:
        cep = self.txt_cep.text().strip()

        def worker(ctx):
            return fetch_cep_info(cep)

        def on_done(info):
            self.table_cep.setRowCount(len(info))
            for row, (k, v) in enumerate(info.items()):
                self.table_cep.setItem(row, 0, QTableWidgetItem(k))
                self.table_cep.setItem(row, 1, QTableWidgetItem(str(v)))

        def on_err(err):
            QMessageBox.warning(self, "Aviso", f"Não foi possível consultar o CEP:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_err)

    # 2. ABA CNPJ
    def _build_cnpj_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("CNPJ (14 dígitos):"))
        self.txt_cnpj = QLineEdit("00000000000191")
        self.txt_cnpj.setFixedWidth(180)
        self.txt_cnpj.returnPressed.connect(self._consult_cnpj)
        row_in.addWidget(self.txt_cnpj)

        btn_consult = QPushButton("Consultar CNPJ")
        btn_consult.setProperty("class", "primary")
        btn_consult.clicked.connect(self._consult_cnpj)
        row_in.addWidget(btn_consult)

        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.clicked.connect(lambda: self._copy_table_content(self.table_cnpj))
        row_in.addWidget(btn_copy)

        row_in.addStretch()
        layout.addLayout(row_in)

        self.table_cnpj = QTableWidget(0, 2)
        self.table_cnpj.setHorizontalHeaderLabels(["Campo", "Informação"])
        self.table_cnpj.horizontalHeader().setStretchLastSection(True)
        self.table_cnpj.verticalHeader().setVisible(False)
        self.table_cnpj.setAlternatingRowColors(True)
        layout.addWidget(self.table_cnpj, stretch=1)

        return tab

    def _consult_cnpj(self) -> None:
        cnpj = self.txt_cnpj.text().strip()

        def worker(ctx):
            return fetch_cnpj_info(cnpj)

        def on_done(info):
            self.table_cnpj.setRowCount(len(info))
            for row, (k, v) in enumerate(info.items()):
                self.table_cnpj.setItem(row, 0, QTableWidgetItem(k))
                self.table_cnpj.setItem(row, 1, QTableWidgetItem(str(v)))

        def on_err(err):
            QMessageBox.warning(self, "Aviso", f"Não foi possível consultar o CNPJ:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_err)

    # 3. ABA DDD
    def _build_ddd_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Código DDD (2 dígitos):"))
        self.txt_ddd = QLineEdit("11")
        self.txt_ddd.setFixedWidth(60)
        self.txt_ddd.returnPressed.connect(self._consult_ddd)
        row_in.addWidget(self.txt_ddd)

        btn_consult = QPushButton("Consultar Cidades do DDD")
        btn_consult.setProperty("class", "primary")
        btn_consult.clicked.connect(self._consult_ddd)
        row_in.addWidget(btn_consult)

        self.lbl_ddd_status = QLabel("Estado: SP | Total: - cidades")
        self.lbl_ddd_status.setStyleSheet("color: #60A5FA; font-weight: bold;")
        row_in.addWidget(self.lbl_ddd_status)

        btn_copy = QPushButton("Copiar Lista de Cidades")
        btn_copy.clicked.connect(self._copy_ddd_cities)
        row_in.addWidget(btn_copy)

        row_in.addStretch()
        layout.addLayout(row_in)

        self.table_ddd_cities = QTableWidget(0, 2)
        self.table_ddd_cities.setHorizontalHeaderLabels(["Nº", "Nome do Município Atendido"])
        self.table_ddd_cities.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_ddd_cities.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_ddd_cities.verticalHeader().setVisible(False)
        self.table_ddd_cities.setAlternatingRowColors(True)
        layout.addWidget(self.table_ddd_cities, stretch=1)

        return tab

    def _consult_ddd(self) -> None:
        ddd = self.txt_ddd.text().strip()

        def worker(ctx):
            return fetch_ddd_info(ddd)

        def on_done(info):
            self.lbl_ddd_status.setText(f"Estado (UF): {info['state']} | Total de Municípios: {info['total_cities']}")
            cities = info["cities"]
            self.table_ddd_cities.setRowCount(len(cities))
            for i, city in enumerate(cities):
                self.table_ddd_cities.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.table_ddd_cities.setItem(i, 1, QTableWidgetItem(city))

        def on_err(err):
            QMessageBox.warning(self, "Aviso", f"Não foi possível consultar o DDD:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_err)

    def _copy_ddd_cities(self) -> None:
        cities = []
        for r in range(self.table_ddd_cities.rowCount()):
            c_item = self.table_ddd_cities.item(r, 1)
            if c_item:
                cities.append(c_item.text())
        if cities:
            QApplication.clipboard().setText("\n".join(cities))
            show_toast(self, f"{len(cities)} municípios copiados!")

    # 4. ABA BANCOS
    def _build_banks_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Filtrar Banco (Código COMPE, Nome ou ISPB):"))
        self.txt_bank_search = QLineEdit()
        self.txt_bank_search.setPlaceholderText("Ex: 001, 237, 260, Nubank, Itaú, Inter...")
        self.txt_bank_search.textChanged.connect(self._filter_banks_local)
        row_in.addWidget(self.txt_bank_search)

        btn_reload = QPushButton("Atualizar Lista do Bacen")
        btn_reload.clicked.connect(self._consult_banks)
        row_in.addWidget(btn_reload)

        btn_copy = QPushButton("Copiar Banco")
        btn_copy.clicked.connect(self._copy_selected_bank)
        row_in.addWidget(btn_copy)

        layout.addLayout(row_in)

        self.table_banks = QTableWidget(0, 4)
        self.table_banks.setHorizontalHeaderLabels(["Código COMPE", "Nome Comercial", "Razão Social Completa", "ISPB"])
        self.table_banks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_banks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_banks.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_banks.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_banks.verticalHeader().setVisible(False)
        self.table_banks.setAlternatingRowColors(True)
        self.table_banks.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_banks, stretch=1)

        self.lbl_banks_count = QLabel("Carregando bancos autorizados pelo Banco Central...")
        self.lbl_banks_count.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        layout.addWidget(self.lbl_banks_count)

        return tab

    def _consult_banks(self) -> None:
        def worker(ctx):
            return fetch_banks()

        def on_done(banks):
            self._all_banks_cache = banks
            self._filter_banks_local()

        def on_err(err):
            self.lbl_banks_count.setText(f"Erro ao carregar bancos: {err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_err)

    def _filter_banks_local(self) -> None:
        query = self.txt_bank_search.text().strip().lower()
        if not query:
            filtered = self._all_banks_cache
        else:
            filtered = [
                b for b in self._all_banks_cache
                if query in b["code"].lower()
                or query in b["name"].lower()
                or query in b["fullName"].lower()
                or query in b["ispb"].lower()
            ]

        self.table_banks.setRowCount(len(filtered))
        for row, b in enumerate(filtered):
            self.table_banks.setItem(row, 0, QTableWidgetItem(b["code"]))
            self.table_banks.setItem(row, 1, QTableWidgetItem(b["name"]))
            self.table_banks.setItem(row, 2, QTableWidgetItem(b["fullName"]))
            self.table_banks.setItem(row, 3, QTableWidgetItem(b["ispb"]))

        self.lbl_banks_count.setText(f"Exibindo {len(filtered)} de {len(self._all_banks_cache)} instituições financeiras.")

    def _copy_selected_bank(self) -> None:
        row = self.table_banks.currentRow()
        if row >= 0:
            code = self.table_banks.item(row, 0).text()
            name = self.table_banks.item(row, 1).text()
            fullname = self.table_banks.item(row, 2).text()
            ispb = self.table_banks.item(row, 3).text()
            text = f"Código: {code} | Nome: {name} | Razão Social: {fullname} | ISPB: {ispb}"
            QApplication.clipboard().setText(text)
            show_toast(self, "Dados do banco copiados!")
        else:
            show_toast(self, "Selecione uma linha da tabela de bancos primeiro.")

    # 5. ABA FERIADOS BRASILAPI
    def _build_holidays_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Ano de Consulta:"))
        self.spin_holidays_year = QSpinBox()
        self.spin_holidays_year.setRange(1900, 2199)
        self.spin_holidays_year.setValue(2026)
        self.spin_holidays_year.setFixedWidth(90)
        row_in.addWidget(self.spin_holidays_year)

        btn_consult = QPushButton("Consultar Feriados Oficiais")
        btn_consult.setProperty("class", "primary")
        btn_consult.clicked.connect(self._consult_holidays)
        row_in.addWidget(btn_consult)

        btn_copy = QPushButton("Copiar Feriados")
        btn_copy.clicked.connect(lambda: self._copy_table_content(self.table_holidays))
        row_in.addWidget(btn_copy)

        row_in.addStretch()
        layout.addLayout(row_in)

        self.table_holidays = QTableWidget(0, 4)
        self.table_holidays.setHorizontalHeaderLabels(["Data", "Dia da Semana", "Feriado Nacional", "Tipo"])
        self.table_holidays.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_holidays.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_holidays.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_holidays.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_holidays.verticalHeader().setVisible(False)
        self.table_holidays.setAlternatingRowColors(True)
        layout.addWidget(self.table_holidays, stretch=1)

        return tab

    def _consult_holidays(self) -> None:
        year = self.spin_holidays_year.value()

        def worker(ctx):
            return fetch_brasilapi_holidays(year)

        def on_done(holidays):
            self.table_holidays.setRowCount(len(holidays))
            for row, h in enumerate(holidays):
                self.table_holidays.setItem(row, 0, QTableWidgetItem(h["formatted_date"]))
                dow_text = h["day_of_week"] + (" (Fim de semana)" if h["is_weekend"] else "")
                self.table_holidays.setItem(row, 1, QTableWidgetItem(dow_text))
                self.table_holidays.setItem(row, 2, QTableWidgetItem(h["name"]))
                self.table_holidays.setItem(row, 3, QTableWidgetItem(h["type"]))

        def on_err(err):
            QMessageBox.warning(self, "Aviso", f"Não foi possível consultar os feriados na BrasilAPI:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_err)

    # 6. ABA TABELA FIPE
    def _build_fipe_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Código FIPE (000000-0):"))
        self.txt_fipe = QLineEdit("001004-9")
        self.txt_fipe.setFixedWidth(120)
        self.txt_fipe.returnPressed.connect(self._consult_fipe)
        row_in.addWidget(self.txt_fipe)

        btn_consult = QPushButton("Consultar Tabela FIPE")
        btn_consult.setProperty("class", "primary")
        btn_consult.clicked.connect(self._consult_fipe)
        row_in.addWidget(btn_consult)

        btn_ex1 = QPushButton("Palio EX (001004-9)")
        btn_ex1.clicked.connect(lambda: self._set_fipe_code("001004-9"))
        row_in.addWidget(btn_ex1)

        btn_ex2 = QPushButton("Corolla XEi (004183-1)")
        btn_ex2.clicked.connect(lambda: self._set_fipe_code("004183-1"))
        row_in.addWidget(btn_ex2)

        row_in.addStretch()
        layout.addLayout(row_in)

        self.table_fipe = QTableWidget(0, 6)
        self.table_fipe.setHorizontalHeaderLabels([
            "Marca / Modelo", "Ano Modelo", "Combustível", "Preço FIPE", "Mês de Referência", "Código FIPE"
        ])
        self.table_fipe.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_fipe.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_fipe.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_fipe.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_fipe.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_fipe.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_fipe.verticalHeader().setVisible(False)
        self.table_fipe.setAlternatingRowColors(True)
        layout.addWidget(self.table_fipe, stretch=1)

        self.lbl_fipe_info = QLabel("Insira o código FIPE com 7 dígitos (ex: 001004-9) para ver histórico e preços atuais.")
        self.lbl_fipe_info.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        layout.addWidget(self.lbl_fipe_info)

        return tab

    def _set_fipe_code(self, code: str) -> None:
        self.txt_fipe.setText(code)
        self._consult_fipe()

    def _consult_fipe(self) -> None:
        code = self.txt_fipe.text().strip()

        def worker(ctx):
            return fetch_fipe_info(code)

        def on_done(items):
            self.table_fipe.setRowCount(len(items))
            for row, item in enumerate(items):
                brand_model = f"{item.get('marca', '')} {item.get('modelo', '')}".strip()
                self.table_fipe.setItem(row, 0, QTableWidgetItem(brand_model))
                self.table_fipe.setItem(row, 1, QTableWidgetItem(str(item.get("anoModelo", "-"))))
                self.table_fipe.setItem(row, 2, QTableWidgetItem(str(item.get("combustivel", "-"))))
                val_item = QTableWidgetItem(str(item.get("valor", "-")))
                val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_fipe.setItem(row, 3, val_item)
                self.table_fipe.setItem(row, 4, QTableWidgetItem(str(item.get("mesReferencia", "-"))))
                self.table_fipe.setItem(row, 5, QTableWidgetItem(str(item.get("codigoFipe", "-"))))

            self.lbl_fipe_info.setText(f"Consulta FIPE concluída: {len(items)} ano(s)/versão(ões) retornada(s).")

        def on_err(err):
            self.lbl_fipe_info.setText(f"Status FIPE: {err}")
            QMessageBox.information(self, "Tabela FIPE", f"{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_err)

    # 7. ABA COTAÇÕES
    def _build_quotes_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        row_act = QHBoxLayout()
        btn_refresh = QPushButton("Atualizar Cotações em Tempo Real")
        btn_refresh.setProperty("class", "primary")
        btn_refresh.clicked.connect(self._refresh_quotes)
        row_act.addWidget(btn_refresh)
        row_act.addStretch()
        layout.addLayout(row_act)

        self.table_quotes = QTableWidget(0, 5)
        self.table_quotes.setHorizontalHeaderLabels([
            "Moeda / Ativo", "Valor de Compra", "Variação Diária", "Máxima", "Mínima"
        ])
        self.table_quotes.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_quotes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_quotes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_quotes.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_quotes.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_quotes.verticalHeader().setVisible(False)
        self.table_quotes.setAlternatingRowColors(True)
        layout.addWidget(self.table_quotes, stretch=1)

        return tab

    def _refresh_quotes(self) -> None:
        def worker(ctx):
            return fetch_currency_quotes()

        def on_done(quotes):
            self._quotes_cache = quotes
            self.table_quotes.setRowCount(len(quotes))
            for row, (coin_name, data) in enumerate(quotes.items()):
                self.table_quotes.setItem(row, 0, QTableWidgetItem(coin_name))
                self.table_quotes.setItem(row, 1, QTableWidgetItem(data["compra"]))
                self.table_quotes.setItem(row, 2, QTableWidgetItem(data["variacao"]))
                self.table_quotes.setItem(row, 3, QTableWidgetItem(data["max"]))
                self.table_quotes.setItem(row, 4, QTableWidgetItem(data["min"]))

        self.runner.start_task(worker, on_finished=on_done)

    def _copy_table_content(self, table: QTableWidget) -> None:
        rows = []
        for r in range(table.rowCount()):
            cols = []
            for c in range(table.columnCount()):
                item = table.item(r, c)
                cols.append(item.text() if item else "")
            rows.append(" | ".join(cols))
        if rows:
            QApplication.clipboard().setText("\n".join(rows))
            show_toast(self, "Tabela copiada para a área de transferência!")
