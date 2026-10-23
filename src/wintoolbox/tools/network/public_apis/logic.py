"""
Lógica pura da ferramenta Consultas Públicas (CEP, CNPJ e Cotações de Moedas/Cripto).
Acessa ViaCEP, BrasilAPI e AwesomeAPI sem acoplamento a UI.
"""
import json
from typing import Dict
import urllib.request


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
            "Código IBGE": data.get("ibge", "-"),
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
            "Capital Social": f"R$ {data.get('capital_social', 0):,.2f}",
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
