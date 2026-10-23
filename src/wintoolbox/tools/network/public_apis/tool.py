"""
Ferramenta: Consultas Públicas (CEP, CNPJ e Cotações de Moedas/Cripto).
Utiliza APIs públicas gratuitas (ViaCEP, BrasilAPI, AwesomeAPI).
"""
import json
import urllib.request
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import fetch_cep_info, fetch_cnpj_info, fetch_currency_quotes

@register
class PublicApisTool(Tool):
    id = "network.public_apis"
    name = "Consultas Públicas (CEP, CNPJ e Cotações)"
    category = "Rede e Internet"
    description = "Consulta de endereços por CEP, dados de empresas por CNPJ e cotações de moedas em tempo real"
    keywords = ["cep", "cnpj", "cotacao", "dolar", "euro", "bitcoin", "moedas", "brasilapi", "viacep", "empresa", "endereco"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PublicApisView(self, parent)

class PublicApisView(QWidget):
    def __init__(self, tool: PublicApisTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._quotes_cache: Dict[str, Dict] = {}

        self._build_ui()
        self._refresh_quotes()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        tabs = QTabWidget()

        # ABA 1: Consulta de CEP
        tab_cep = QWidget()
        l_cep = QVBoxLayout(tab_cep)
        l_cep.setSpacing(10)

        row_cep_in = QHBoxLayout()
        row_cep_in.addWidget(QLabel("Digite o CEP:"))
        self.txt_cep = QLineEdit("01001-000")
        self.txt_cep.setFixedWidth(130)
        row_cep_in.addWidget(self.txt_cep)

        btn_consult_cep = QPushButton("Consultar CEP")
        btn_consult_cep.setProperty("class", "primary")
        btn_consult_cep.clicked.connect(self._consult_cep)
        row_cep_in.addWidget(btn_consult_cep)
        row_cep_in.addStretch()
        l_cep.addLayout(row_cep_in)

        self.table_cep = QTableWidget(0, 2)
        self.table_cep.setHorizontalHeaderLabels(["Campo", "Informação"])
        self.table_cep.horizontalHeader().setStretchLastSection(True)
        self.table_cep.verticalHeader().setVisible(False)
        self.table_cep.setFixedHeight(230)
        l_cep.addWidget(self.table_cep)
        tabs.addTab(tab_cep, "Consulta de CEP")

        # ABA 2: Consulta de CNPJ
        tab_cnpj = QWidget()
        l_cnpj = QVBoxLayout(tab_cnpj)
        l_cnpj.setSpacing(10)

        row_cnpj_in = QHBoxLayout()
        row_cnpj_in.addWidget(QLabel("Digite o CNPJ:"))
        self.txt_cnpj = QLineEdit("00000000000191")
        self.txt_cnpj.setFixedWidth(180)
        row_cnpj_in.addWidget(self.txt_cnpj)

        btn_consult_cnpj = QPushButton("Consultar CNPJ")
        btn_consult_cnpj.setProperty("class", "primary")
        btn_consult_cnpj.clicked.connect(self._consult_cnpj)
        row_cnpj_in.addWidget(btn_consult_cnpj)
        row_cnpj_in.addStretch()
        l_cnpj.addLayout(row_cnpj_in)

        self.table_cnpj = QTableWidget(0, 2)
        self.table_cnpj.setHorizontalHeaderLabels(["Campo", "Informação"])
        self.table_cnpj.horizontalHeader().setStretchLastSection(True)
        self.table_cnpj.verticalHeader().setVisible(False)
        self.table_cnpj.setFixedHeight(250)
        l_cnpj.addWidget(self.table_cnpj)
        tabs.addTab(tab_cnpj, "Consulta de CNPJ")

        # ABA 3: Cotações de Moedas e Cripto
        tab_quotes = QWidget()
        l_quotes = QVBoxLayout(tab_quotes)
        l_quotes.setSpacing(10)

        row_q_act = QHBoxLayout()
        btn_refresh_q = QPushButton("Atualizar Cotações")
        btn_refresh_q.clicked.connect(self._refresh_quotes)
        row_q_act.addWidget(btn_refresh_q)
        row_q_act.addStretch()
        l_quotes.addLayout(row_q_act)

        self.table_quotes = QTableWidget(0, 5)
        self.table_quotes.setHorizontalHeaderLabels([
            "Moeda / Ativo", "Valor de Compra", "Variação Diária", "Máxima", "Mínima"
        ])
        self.table_quotes.horizontalHeader().setStretchLastSection(True)
        self.table_quotes.verticalHeader().setVisible(False)
        self.table_quotes.setFixedHeight(180)
        l_quotes.addWidget(self.table_quotes)

        tabs.addTab(tab_quotes, "Cotações de Moedas e Cripto")

        layout.addWidget(tabs)
        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _consult_cep(self):
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

    def _consult_cnpj(self):
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

    def _refresh_quotes(self):
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
