"""
Testes unitários para o controle de finanças pessoais (OFX, CSV e balanço).
Diretrizes Anti-Gambiarra: Validação real de dados e asserções determinísticas.
"""
from pathlib import Path
from wintoolbox.tools.productivity.finance_tracker.logic import (
    Transaction,
    calculate_balance_summary,
    guess_category,
    parse_csv_bank_statement,
    parse_ofx_date,
    parse_ofx_file,
)


def test_guess_category():
    assert guess_category("Pagamento Ifood Refeição", -45.50) == "Alimentação"
    assert guess_category("Corrida Uber Viagem", -22.30) == "Transporte"
    assert guess_category("Farmacia Drogasil", -85.00) == "Saúde"
    assert guess_category("Mensalidade Netflix", -55.90) == "Lazer"
    assert guess_category("Folha de Pagamento Salário", 5000.00) == "Salário"
    assert guess_category("Transferência Desconhecida", -10.00) == "Outros"


def test_parse_ofx_date():
    assert parse_ofx_date("20261025120000[-03:EST]") == "2026-10-25"
    assert parse_ofx_date("20260101") == "2026-01-01"


def test_parse_ofx_file_real(tmp_path: Path):
    ofx_content = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILESPEC:NONE
NEWFILESPEC:NONE

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>20261020120000[-03:EST]
            <TRNAMT>-85.50
            <FITID>20261020001
            <MEMO>SUPERMERCADO DIA
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20261022120000[-03:EST]
            <TRNAMT>3500.00
            <FITID>20261022002
            <NAME>TED RECEBIDA SALARIO EMPRESA
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""
    file_path = tmp_path / "extrato.ofx"
    file_path.write_text(ofx_content, encoding="utf-8")

    txs = parse_ofx_file(file_path, "Banco XPTO")
    assert len(txs) == 2

    assert txs[0].amount == -85.50
    assert txs[0].date == "2026-10-20"
    assert txs[0].description == "SUPERMERCADO DIA"
    assert txs[0].category == "Alimentação"
    assert txs[0].account == "Banco XPTO"

    assert txs[1].amount == 3500.00
    assert txs[1].date == "2026-10-22"
    assert txs[1].description == "TED RECEBIDA SALARIO EMPRESA"
    assert txs[1].category == "Salário"


def test_parse_csv_bank_statement_real(tmp_path: Path):
    csv_content = """Data,Descrição,Valor
25/10/2026,POSTO SHELL GASOLINA,-150,00
26/10/2026,PIX RECEBIDO CLIENTE,800,00
"""
    file_path = tmp_path / "extrato.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    txs = parse_csv_bank_statement(file_path, delimiter=",", account_name="Nubank")
    assert len(txs) == 2

    assert txs[0].date == "2026-10-25"
    assert txs[0].description == "POSTO SHELL GASOLINA"
    assert txs[0].amount == -150.00
    assert txs[0].category == "Transporte"
    assert txs[0].account == "Nubank"

    assert txs[1].date == "2026-10-26"
    assert txs[1].description == "PIX RECEBIDO CLIENTE"
    assert txs[1].amount == 800.00
    assert txs[1].category == "Salário"


def test_calculate_balance_summary():
    transactions = [
        Transaction(id="1", date="2026-10-01", description="Salário", amount=5000.00, category="Salário"),
        Transaction(id="2", date="2026-10-05", description="Aluguel", amount=-1500.00, category="Moradia"),
        Transaction(id="3", date="2026-10-10", description="Mercado", amount=-600.00, category="Alimentação"),
        Transaction(id="4", date="2026-10-15", description="Restaurante", amount=-150.00, category="Alimentação"),
    ]

    summary = calculate_balance_summary(transactions)
    assert summary["total_income"] == 5000.00
    assert summary["total_expense"] == 2250.00
    assert summary["balance"] == 2750.00
    assert summary["categories_breakdown"]["Moradia"] == 1500.00
    assert summary["categories_breakdown"]["Alimentação"] == 750.00
