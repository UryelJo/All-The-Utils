"""
Lógica pura da ferramenta Consultas Públicas (CEP, CNPJ, Cotações, DDD, Bancos, Feriados e FIPE).
Acessa ViaCEP, BrasilAPI e AwesomeAPI sem acoplamento à interface gráfica.
"""
from datetime import datetime
import json
from typing import Any, Dict, List, NoReturn, Optional
import urllib.error
import urllib.request


def fetch_cep_info(cep: str) -> Dict[str, str]:
    """Consulta dados de endereço a partir do CEP via ViaCEP."""
    clean_cep = "".join(filter(str.isdigit, cep))
    if len(clean_cep) != 8:
        raise ValueError("O CEP deve conter exatamente 8 dígitos numéricos.")

    url = f"https://viacep.com.br/ws/{clean_cep}/json/"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
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
            "Código IBGE": data.get("ibge", "-"),
        }


def fetch_cnpj_info(cnpj: str) -> Dict[str, str]:
    """Consulta dados cadastrais de empresa a partir do CNPJ via BrasilAPI."""
    clean_cnpj = "".join(filter(str.isdigit, cnpj))
    if len(clean_cnpj) != 14:
        raise ValueError("O CNPJ deve conter exatamente 14 dígitos numéricos.")

    url = f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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
                "Capital Social": f"R$ {float(data.get('capital_social', 0)):,.2f}",
            }
    except urllib.error.HTTPError as e:
        _handle_brasilapi_error(e, "CNPJ")


def fetch_currency_quotes() -> Dict[str, Dict[str, Any]]:
    """Consulta cotações de moedas e criptomoedas em tempo real via AwesomeAPI."""
    url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-BRL,ETH-BRL"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        quotes: Dict[str, Dict[str, Any]] = {}
        names_map = {
            "USDBRL": "Dólar Comercial (USD)",
            "EURBRL": "Euro (EUR)",
            "BTCBRL": "Bitcoin (BTC)",
            "ETHBRL": "Ethereum (ETH)",
        }
        for k, v in data.items():
            name = names_map.get(k, k)
            quotes[name] = {
                "compra": f"R$ {float(v.get('bid', 0)):,.2f}",
                "venda": f"R$ {float(v.get('ask', 0)):,.2f}",
                "variacao": f"{float(v.get('pctChange', 0)):+.2f}%",
                "max": f"R$ {float(v.get('high', 0)):,.2f}",
                "min": f"R$ {float(v.get('low', 0)):,.2f}",
                "raw_bid": float(v.get("bid", 1.0)),
            }
        return quotes


def fetch_ddd_info(ddd_code: str | int) -> Dict[str, Any]:
    """Consulta estado e municípios atendidos por um código DDD via BrasilAPI."""
    clean_ddd = "".join(filter(str.isdigit, str(ddd_code)))
    if len(clean_ddd) != 2:
        raise ValueError("O DDD deve conter exatamente 2 dígitos (ex: 11, 21, 31, 85).")

    url = f"https://brasilapi.com.br/api/ddd/v1/{clean_ddd}"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cities = sorted(data.get("cities", []))
            return {
                "ddd": clean_ddd,
                "state": data.get("state", "-"),
                "cities": cities,
                "total_cities": len(cities),
            }
    except urllib.error.HTTPError as e:
        _handle_brasilapi_error(e, "DDD")


def fetch_banks(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Consulta lista de instituições bancárias autorizadas pelo Banco Central via BrasilAPI."""
    url = "https://brasilapi.com.br/api/banks/v1"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            banks = json.loads(resp.read().decode("utf-8"))
            if not isinstance(banks, list):
                return []

            # Trata itens nulos e formata código
            normalized = []
            for b in banks:
                code_raw = b.get("code")
                code_str = f"{code_raw:03d}" if isinstance(code_raw, int) else (str(code_raw or "-"))
                normalized.append({
                    "code": code_str,
                    "name": b.get("name") or "-",
                    "fullName": b.get("fullName") or b.get("name") or "-",
                    "ispb": str(b.get("ispb") or "-"),
                })

            if search:
                query = search.strip().lower()
                normalized = [
                    b for b in normalized
                    if query in b["code"].lower()
                    or query in b["name"].lower()
                    or query in b["fullName"].lower()
                    or query in b["ispb"].lower()
                ]

            return sorted(normalized, key=lambda x: (x["code"] == "-", x["code"], x["name"]))
    except urllib.error.HTTPError as e:
        _handle_brasilapi_error(e, "Bancos")


def fetch_brasilapi_holidays(year: int) -> List[Dict[str, Any]]:
    """Consulta os feriados nacionais oficiais registrados para um ano via BrasilAPI."""
    if year < 1900 or year > 2199:
        raise ValueError("O ano deve estar entre 1900 e 2199.")

    url = f"https://brasilapi.com.br/api/feriados/v1/{year}"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw_list = json.loads(resp.read().decode("utf-8"))
            if not isinstance(raw_list, list):
                return []

            dow_names = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
            formatted = []
            for h in raw_list:
                dt_str = h.get("date", "")
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                    f_date = dt.strftime("%d/%m/%Y")
                    dow = dow_names[dt.weekday()]
                    is_weekend = dt.weekday() >= 5
                except Exception:
                    f_date = dt_str
                    dow = "-"
                    is_weekend = False

                formatted.append({
                    "date": dt_str,
                    "formatted_date": f_date,
                    "name": h.get("name", "-"),
                    "type": h.get("type", "national"),
                    "day_of_week": dow,
                    "is_weekend": is_weekend,
                })

            return formatted
    except urllib.error.HTTPError as e:
        _handle_brasilapi_error(e, "Feriados")


def fetch_fipe_info(codigo_fipe: str) -> List[Dict[str, Any]]:
    """
    Consulta o valor e especificações de veículos na Tabela FIPE a partir do código FIPE.
    Exemplos de código: 004183-1, 001004-9.
    """
    raw = codigo_fipe.strip().replace(" ", "").replace(".", "")
    if "-" not in raw and len(raw) == 7:
        clean_code = f"{raw[:6]}-{raw[6]}"
    else:
        clean_code = raw

    if len(clean_code) != 8 or clean_code[6] != "-":
        raise ValueError("Código FIPE inválido. Use o formato 000000-0 (7 dígitos e hífen).")

    url = f"https://brasilapi.com.br/api/fipe/preco/v1/{clean_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            return []
    except urllib.error.HTTPError as e:
        _handle_brasilapi_error(e, "Tabela FIPE")


def _handle_brasilapi_error(err: urllib.error.HTTPError, resource_name: str) -> NoReturn:
    """Extrai e propaga mensagem de erro amigável retornada pela API ou padrão HTTP."""
    server_msg = None
    try:
        raw_body = err.read().decode("utf-8", errors="ignore")
        data = json.loads(raw_body)
        if isinstance(data, dict) and data.get("message"):
            server_msg = str(data["message"]).strip()
    except (json.JSONDecodeError, UnicodeDecodeError, Exception):
        pass

    if server_msg:
        raise ValueError(f"{resource_name}: {server_msg}")

    if err.code == 404:
        raise ValueError(f"{resource_name} não localizado na base de dados (404 Not Found).")
    elif err.code == 500:
        raise ValueError(f"O serviço da BrasilAPI para {resource_name} está temporariamente instável ou indisponível (HTTP 500).")
    elif err.code == 502:
        raise ValueError(f"Serviço da BrasilAPI indisponível temporariamente (HTTP 502 Bad Gateway).")
    elif err.code == 503:
        raise ValueError(f"Serviço da BrasilAPI em manutenção ou sobrecarregado (HTTP 503).")
    raise ValueError(f"Falha na consulta de {resource_name} (HTTP {err.code}): {err.reason}")

