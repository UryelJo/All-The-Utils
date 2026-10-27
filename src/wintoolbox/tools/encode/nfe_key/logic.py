"""
Lógica pura para validação, decodificação e análise da chave de acesso de 44 dígitos
de Documentos Fiscais Eletrônicos brasileiros (NF-e, NFC-e, CT-e, MDF-e).

Padrão oficial SEFAZ / ENCAT:
- cUF (2 dígitos): Código da UF
- AAMM (4 dígitos): Ano e Mês de emissão
- CNPJ (14 dígitos): CNPJ do emitente
- mod (2 dígitos): Modelo (55: NF-e, 65: NFC-e, 57: CT-e, 58: MDF-e)
- serie (3 dígitos): Série do documento
- nNF (9 dígitos): Número do documento
- tpEmis (1 dígito): Tipo de emissão (1: Normal, 2-9: Contingências)
- cNF (8 dígitos): Código numérico aleatório
- cDV (1 dígito): Dígito verificador (Módulo 11 com pesos de 2 a 9)

Isolado de qualquer biblioteca de interface gráfica.
"""
from dataclasses import dataclass
import random
import re
from typing import Dict, Optional


UF_IBGE: Dict[str, str] = {
    "11": "Rondônia (RO)",
    "12": "Acre (AC)",
    "13": "Amazonas (AM)",
    "14": "Roraima (RR)",
    "15": "Pará (PA)",
    "16": "Amapá (AP)",
    "17": "Tocantins (TO)",
    "21": "Maranhão (MA)",
    "22": "Piauí (PI)",
    "23": "Ceará (CE)",
    "24": "Rio Grande do Norte (RN)",
    "25": "Paraíba (PB)",
    "26": "Pernambuco (PE)",
    "27": "Alagoas (AL)",
    "28": "Sergipe (SE)",
    "29": "Bahia (BA)",
    "31": "Minas Gerais (MG)",
    "32": "Espírito Santo (ES)",
    "33": "Rio de Janeiro (RJ)",
    "35": "São Paulo (SP)",
    "41": "Paraná (PR)",
    "42": "Santa Catarina (SC)",
    "43": "Rio Grande do Sul (RS)",
    "50": "Mato Grosso do Sul (MS)",
    "51": "Mato Grosso (MT)",
    "52": "Goiás (GO)",
    "53": "Distrito Federal (DF)",
}

MODELOS_DFE: Dict[str, str] = {
    "55": "NF-e (Nota Fiscal Eletrônica)",
    "57": "CT-e (Conhecimento de Transporte Eletrônico)",
    "58": "MDF-e (Manifesto Eletrônico de Documentos Fiscais)",
    "59": "CF-e SAT (Cupom Fiscal Eletrônico)",
    "65": "NFC-e (Nota Fiscal de Consumidor Eletrônica)",
}

TIPOS_EMISSAO: Dict[str, str] = {
    "1": "Emissão Normal",
    "2": "Contingência FS-IA",
    "3": "Contingência SCAN",
    "4": "Contingência DPEC",
    "5": "Contingência FS-DA",
    "6": "Contingência SVC-AN",
    "7": "Contingência SVC-RS",
    "9": "Contingência Off-line da NFC-e",
}


@dataclass(frozen=True)
class NFeKeyInfo:
    """Dados estruturados decodificados da chave de acesso NF-e."""
    is_valid: bool
    raw_key: str
    uf_codigo: str
    uf_nome: str
    ano_mes: str
    data_emissao_formatada: str
    cnpj_emitente: str
    cnpj_formatado: str
    modelo_codigo: str
    modelo_nome: str
    serie: int
    numero_nota: int
    tipo_emissao_codigo: str
    tipo_emissao_nome: str
    codigo_numerico: str
    digito_verificador: int
    dv_calculado: int
    erro_mensagem: str = ""


def calcular_dv_nfe(chave_43: str) -> int:
    """
    Cálculo do Dígito Verificador Módulo 11 da Chave de Acesso NF-e (43 primeiros dígitos).
    Pesos de 2 a 9 da direita para a esquerda.
    Resto 0 ou 1 -> DV = 0.
    Outros restos -> DV = 11 - resto.
    """
    soma = 0
    peso = 2
    for d in reversed(chave_43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1

    resto = soma % 11
    if resto in (0, 1):
        return 0
    return 11 - resto


def format_cnpj(cnpj: str) -> str:
    """Formata 14 dígitos numéricos no padrão XX.XXX.XXX/XXXX-XX."""
    c = re.sub(r"\D", "", cnpj)
    if len(c) == 14:
        return f"{c[0:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}"
    return cnpj


def format_nfe_key(key: str) -> str:
    """Formata a chave de 44 dígitos em grupos de 4 dígitos para fácil leitura."""
    digits = re.sub(r"\D", "", key)
    if len(digits) == 44:
        return " ".join(digits[i:i+4] for i in range(0, 44, 4))
    return key


def decode_nfe_key(raw_key: str) -> NFeKeyInfo:
    """
    Decodifica e valida a chave de acesso fiscal de 44 dígitos.
    """
    digits = re.sub(r"\D", "", raw_key.strip())

    if len(digits) != 44:
        return NFeKeyInfo(
            is_valid=False,
            raw_key=digits,
            uf_codigo="",
            uf_nome="",
            ano_mes="",
            data_emissao_formatada="",
            cnpj_emitente="",
            cnpj_formatado="",
            modelo_codigo="",
            modelo_nome="",
            serie=0,
            numero_nota=0,
            tipo_emissao_codigo="",
            tipo_emissao_nome="",
            codigo_numerico="",
            digito_verificador=0,
            dv_calculado=0,
            erro_mensagem=f"A chave deve conter exatamente 44 dígitos numéricos (recebido {len(digits)}).",
        )

    uf_cod = digits[0:2]
    ano_mes_raw = digits[2:6]
    cnpj_raw = digits[6:20]
    mod_cod = digits[20:22]
    serie_raw = digits[22:25]
    n_nf_raw = digits[25:34]
    tp_emis = digits[34]
    c_nf = digits[35:43]
    dv_informado = int(digits[43])

    # Cálculo do DV
    dv_calculado = calcular_dv_nfe(digits[0:43])
    is_valid = (dv_informado == dv_calculado)
    err = "" if is_valid else f"Dígito verificador inválido (esperado {dv_calculado}, recebido {dv_informado})."

    # Formatação de Ano e Mês
    ano = f"20{ano_mes_raw[0:2]}"
    mes = ano_mes_raw[2:4]
    meses_pt = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
        "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
        "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
    }
    data_formatada = f"{meses_pt.get(mes, mes)} / {ano}"

    return NFeKeyInfo(
        is_valid=is_valid,
        raw_key=digits,
        uf_codigo=uf_cod,
        uf_nome=UF_IBGE.get(uf_cod, f"UF {uf_cod} (Desconhecida)"),
        ano_mes=ano_mes_raw,
        data_emissao_formatada=data_formatada,
        cnpj_emitente=cnpj_raw,
        cnpj_formatado=format_cnpj(cnpj_raw),
        modelo_codigo=mod_cod,
        modelo_nome=MODELOS_DFE.get(mod_cod, f"Modelo {mod_cod} (Outro)"),
        serie=int(serie_raw),
        numero_nota=int(n_nf_raw),
        tipo_emissao_codigo=tp_emis,
        tipo_emissao_nome=TIPOS_EMISSAO.get(tp_emis, f"Tipo {tp_emis}"),
        codigo_numerico=c_nf,
        digito_verificador=dv_informado,
        dv_calculado=dv_calculado,
        erro_mensagem=err,
    )


def generate_sample_nfe_key(uf: str = "35", modelo: str = "55") -> str:
    """Gera uma chave sintética com DV matematicamente válido para testes."""
    ano_mes = "2603"
    cnpj = "00000000000191"
    serie = "001"
    n_nf = "000123456"
    tp_emis = "1"
    c_nf = f"{random.randint(10000000, 99999999)}"

    chave_43 = f"{uf}{ano_mes}{cnpj}{modelo}{serie}{n_nf}{tp_emis}{c_nf}"
    dv = calcular_dv_nfe(chave_43)
    return f"{chave_43}{dv}"
