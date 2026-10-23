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

def fetch_cep_info(cep: str) -> Dict[str, str]:
    """Consulta dados de endereço a partir do CEP via ViaCEP."""
    clean_cep = "".join(filter(str.isdigit, cep))
    if len(clean_cep) != 8:
        raise ValueError("O CEP deve conter exatamente 8 dígitos numéricos.")

    url = f"https://viacep.com.br/ws/{clean_cep}/json/"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("erro"):
            raise ValueError("CEP não localizado na base dos Correios.")
        return {
            "CEP": data.get("cep", ""),
            "Logradouro": data.get("logradouro", "-"),
            "Complemento": data.get("complemento", "-"),
            "Bairro": data.get("bairro", "-"),
            "Cidade": data.get("localidade", "-"),
            "Estado (UF)": data.get("uf", "-"),
            "DDD": data.get("ddd", "-"),
            "Código IBGE": data.get("ibge", "-")
        }

def fetch_cnpj_info(cnpj: str) -> Dict[str, str]:
    """Consulta dados cadastrais de empresa a partir do CNPJ via BrasilAPI."""
    clean_cnpj = "".join(filter(str.isdigit, cnpj))
    if len(clean_cnpj) != 14:
        raise ValueError("O CNPJ deve conter exatamente 14 dígitos numéricos.")

    url = f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return {
            "CNPJ": data.get("cnpj", clean_cnpj),
            "Razão Social": data.get("razao_social", "-"),
            "Nome Fantasia": data.get("nome_fantasia", "-") or "-",
            "Situação Cadastral": data.get("descricao_situacao_cadastral", "-"),
            "Data de Abertura": data.get("data_inicio_atividade", "-"),
            "CNAE Principal": f"{data.get('cnae_fiscal', '')} - {data.get('cnae_fiscal_descricao', '')}",
            "Natureza Jurídica": data.get("natureza_juridica", "-"),
            "Município / UF": f"{data.get('municipio', '')} / {data.get('uf', '')}",
            "Bairro / Logradouro": f"{data.get('logradouro', '')}, {data.get('numero', '')} - {data.get('bairro', '')}",
            "Capital Social": f"R$ {data.get('capital_social', 0):,.2f}"
        }

def fetch_currency_quotes() -> Dict[str, Dict[str, str]]:
    """Consulta cotações de moedas e criptomoedas em tempo real via AwesomeAPI."""
    url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-BRL,ETH-BRL"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        quotes = {}
        names_map = {
            "USDBRL": "Dólar Comercial (USD)",
            "EURBRL": "Euro (EUR)",
            "BTCBRL": "Bitcoin (BTC)",
            "ETHBRL": "Ethereum (ETH)"
        }
        for k, v in data.items():
            name = names_map.get(k, k)
            quotes[name] = {
                "compra": f"R$ {float(v.get('bid', 0)):,.2f}",
                "venda": f"R$ {float(v.get('ask', 0)):,.2f}",
                "variacao": f"{float(v.get('pctChange', 0)):+.2f}%",
                "max": f"R$ {float(v.get('high', 0)):,.2f}",
                "min": f"R$ {float(v.get('low', 0)):,.2f}",
                "raw_bid": float(v.get("bid", 1.0))
            }
        return quotes

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
