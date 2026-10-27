"""
Lógica pura para controle de finanças pessoais offline.
Suporta parsing de extratos bancários brasileiros nos formatos OFX e CSV,
categorização heurística de despesas e cálculo de saldos e balanços.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import csv
import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CATEGORIES = [
    "Alimentação", "Transporte", "Moradia", "Saúde", "Educação",
    "Lazer", "Serviços", "Salário", "Investimentos", "Outros"
]

CATEGORY_KEYWORDS = {
    "Alimentação": ["ifood", "restaurante", "supermercado", "mercado", "padaria", "mcdonalds", "burger", "hortifruti", "acougue", "cafe"],
    "Transporte": ["uber", "99app", "posto", "combustivel", "gasolina", "estacionamento", "pedagio", "metro", "onibus"],
    "Saúde": ["farmacia", "drogaria", "droga", "hospital", "clinica", "medico", "dentista", "laboratorio", "consulta"],
    "Moradia": ["aluguel", "condominio", "energia", "enel", "sabesp", "agua", "internet", "claro", "vivo", "luz", "botijao", "gas natural", "ultragaz"],
    "Educação": ["curso", "faculdade", "udemy", "alura", "livraria", "escola", "idiomas"],
    "Lazer": ["netflix", "spotify", "cinema", "ingresso", "steam", "playstation", "jogo", "viagem", "hotel"],
    "Serviços": ["apple", "google", "amazon", "microsoft", "iof", "tarifa", "anuidade"],
    "Salário": ["salario", "folha", "ted recebida", "pix recebido", "remuneracao", "pro-labore"],
    "Investimentos": ["cdb", "tesouro", "rendimento", "dividendos", "fii", "aplicacao", "poupanca"],
}


@dataclass
class Transaction:
    """Representa uma transação financeira individual."""
    id: str
    date: str  # YYYY-MM-DD
    description: str
    amount: float  # Positivo para receitas, negativo para despesas
    category: str
    account: str = "Padrão"


def guess_category(description: str, amount: float) -> str:
    """Sugere uma categoria com base na descrição e sinal do valor."""
    desc_lower = description.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if w in desc_lower:
                return cat

    if amount > 0:
        return "Salário" if "pagamento" in desc_lower else "Investimentos"
    return "Outros"


def parse_ofx_date(date_str: str) -> str:
    """Converte formato de data OFX (ex: 20261025120000[-03:EST]) para YYYY-MM-DD."""
    clean = re.sub(r'\[.*\]', '', date_str.strip())
    if len(clean) >= 8:
        year = clean[0:4]
        month = clean[4:6]
        day = clean[6:8]
        return f"{year}-{month}-{day}"
    return datetime.now().strftime("%Y-%m-%d")


def parse_ofx_file(file_path: Path, account_name: str = "Banco") -> List[Transaction]:
    """Interpreta extrato bancário no formato padrão Open Financial Exchange (OFX)."""
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo OFX não encontrado: {file_path}")

    content = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue

    transactions: List[Transaction] = []

    # Procura blocos <STMTTRN> ... </STMTTRN>
    pattern = re.compile(r'<STMTTRN>([\s\S]*?)(?:</STMTTRN>|(?=<STMTTRN>|\Z))', re.IGNORECASE)
    for match in pattern.finditer(content):
        block = match.group(1)

        # Extrai campos
        m_amt = re.search(r'<TRNAMT>([\s\S]*?)(?:<|\n|\r)', block, re.IGNORECASE)
        m_date = re.search(r'<DTPOSTED>([\s\S]*?)(?:<|\n|\r)', block, re.IGNORECASE)
        m_memo = re.search(r'<MEMO>([\s\S]*?)(?:<|\n|\r)', block, re.IGNORECASE)
        m_name = re.search(r'<NAME>([\s\S]*?)(?:<|\n|\r)', block, re.IGNORECASE)

        if not m_amt or not m_date:
            continue

        amt_str = m_amt.group(1).strip().replace(",", ".")
        try:
            amount = float(amt_str)
        except ValueError:
            continue

        date_str = parse_ofx_date(m_date.group(1).strip())
        desc = ""
        if m_name and m_name.group(1).strip():
            desc = m_name.group(1).strip()
        elif m_memo and m_memo.group(1).strip():
            desc = m_memo.group(1).strip()
        else:
            desc = "Transação Bancária"

        cat = guess_category(desc, amount)
        transactions.append(
            Transaction(
                id=str(uuid.uuid4())[:8],
                date=date_str,
                description=desc,
                amount=amount,
                category=cat,
                account=account_name
            )
        )

    return transactions


def parse_csv_bank_statement(file_path: Path, account_name: str = "Conta", delimiter: Optional[str] = None) -> List[Transaction]:
    """Interpreta extratos bancários em formato CSV com detecção de colunas brasileiras."""
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {file_path}")

    content = ""
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue

    lines = [l for l in content.splitlines() if l.strip()]
    if not lines:
        return []

    # Detecta delimitador se não foi explicitamente fornecido
    if delimiter:
        delim = delimiter
    else:
        sample = lines[0]
        delim = ";" if ";" in sample else ","

    reader = csv.reader(lines, delimiter=delim)
    header = [h.strip().lower() for h in next(reader, [])]

    # Localiza índices de data, valor e descrição
    idx_date = -1
    idx_desc = -1
    idx_amount = -1

    for i, col in enumerate(header):
        if any(w in col for w in ["data", "date", "dt"]):
            idx_date = i
        elif any(w in col for w in ["descricao", "descrição", "historico", "histórico", "memo", "title", "nome"]):
            idx_desc = i
        elif any(w in col for w in ["valor", "amount", "quantia"]):
            idx_amount = i

    if idx_date == -1 or idx_amount == -1:
        # Fallback para primeiras 3 colunas comuns: Data, Descricao, Valor
        idx_date, idx_desc, idx_amount = 0, 1, 2

    transactions: List[Transaction] = []

    for row in reader:
        if len(row) <= max(idx_date, idx_desc, idx_amount):
            continue

        raw_date = row[idx_date].strip()
        raw_desc = row[idx_desc].strip() if idx_desc < len(row) else "Transação"
        raw_val = row[idx_amount].strip().replace("R$", "").replace(" ", "")

        # Trata formato monetário brasileiro (ex: -1.250,50 -> -1250.50)
        if "," in raw_val and "." in raw_val:
            raw_val = raw_val.replace(".", "").replace(",", ".")
        elif "," in raw_val:
            raw_val = raw_val.replace(",", ".")

        try:
            val = float(raw_val)
        except ValueError:
            continue

        # Normaliza data DD/MM/YYYY para YYYY-MM-DD
        date_iso = raw_date
        if "/" in raw_date:
            parts = raw_date.split("/")
            if len(parts) == 3:
                day, month, year = parts
                if len(year) == 2:
                    year = "20" + year
                date_iso = f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"

        cat = guess_category(raw_desc, val)
        transactions.append(
            Transaction(
                id=str(uuid.uuid4())[:8],
                date=date_iso,
                description=raw_desc,
                amount=val,
                category=cat,
                account=account_name
            )
        )

    return transactions


def calculate_balance_summary(transactions: List[Transaction]) -> Dict[str, Any]:
    """Calcula saldo total, total de receitas, despesas e gastos por categoria."""
    income = 0.0
    expense = 0.0
    categories_breakdown: Dict[str, float] = {}

    for t in transactions:
        if t.amount >= 0:
            income += t.amount
        else:
            expense += abs(t.amount)
            categories_breakdown[t.category] = categories_breakdown.get(t.category, 0.0) + abs(t.amount)

    balance = income - expense
    return {
        "balance": balance,
        "total_income": income,
        "total_expense": expense,
        "categories_breakdown": categories_breakdown,
        "transaction_count": len(transactions)
    }
