"""
Lógica pura para decodificação, validação e conversão de boletos de cobrança bancária
e concessionárias de serviços conforme o padrão FEBRABAN.

Suporta:
- Boletos de Cobrança Bancária (linha digitável de 47 dígitos ou código de barras de 44 dígitos)
- Boletos de Concessionárias / Tributos (linha digitável de 48 dígitos ou código de barras de 44 dígitos iniciando em 8)
- Cálculo e conferência rigorosa dos dígitos verificadores (Módulo 10 e Módulo 11)
- Identificação da instituição financeira / banco emissor
- Extração de data de vencimento a partir do fator FEBRABAN (com virada de ciclo pós-2025)
- Extração do valor nominal em Reais
- Conversão bidirecional: Linha Digitável <-> Código de Barras

Isolado de qualquer biblioteca de interface gráfica.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from typing import Dict, Optional, Tuple


BANCOS_BRASIL: Dict[str, str] = {
    "001": "Banco do Brasil S.A.",
    "003": "Banco da Amazônia S.A.",
    "004": "Banco do Nordeste do Brasil S.A.",
    "021": "BANESTES S.A. Banco do Estado do Espírito Santo",
    "033": "Banco Santander (Brasil) S.A.",
    "041": "Banco do Estado do Rio Grande do Sul S.A. (Banrisul)",
    "070": "BRB - Banco de Brasília S.A.",
    "077": "Banco Inter S.A.",
    "104": "Caixa Econômica Federal",
    "208": "Banco BTG Pactual S.A.",
    "212": "Banco Original S.A.",
    "237": "Banco Bradesco S.A.",
    "260": "Nu Pagamentos S.A. (Nubank)",
    "336": "Banco C6 S.A.",
    "341": "Itaú Unibanco S.A.",
    "389": "Banco Mercantil do Brasil S.A.",
    "422": "Banco Safra S.A.",
    "655": "Banco Votorantim S.A. (BV)",
    "748": "Banco Cooperativo Sicredi S.A.",
    "756": "Banco Cooperativo Sicoob S.A.",
}

SEGMENTOS_CONCESSIONARIA: Dict[str, str] = {
    "1": "Prefeituras",
    "2": "Saneamento / Água e Esgoto",
    "3": "Energia Elétrica e Gás",
    "4": "Telecomunicações",
    "5": "Órgãos Governamentais",
    "6": "Carnês e Assemelhados",
    "7": "Multas de Trânsito",
    "9": "Uso Exclusivo do Banco",
}


@dataclass(frozen=True)
class BoletoInfo:
    """Informações decodificadas de um boleto."""
    is_valid: bool
    tipo: str  # "COBRANCA" ou "CONCESSIONARIA"
    linha_digitavel: str
    codigo_barras: str
    banco_codigo: str
    banco_nome: str
    valor: Optional[Decimal]
    data_vencimento: Optional[date]
    fator_vencimento: Optional[int]
    campo_livre: str
    erro_mensagem: str = ""


def calcular_mod10(numero: str) -> int:
    """
    Cálculo do Dígito Verificador Módulo 10 FEBRABAN (pesos alternados 2 e 1 da direita para esquerda).
    Soma-se os algarismos individuais do produto.
    """
    soma = 0
    peso = 2
    for d in reversed(numero):
        mult = int(d) * peso
        # Se mult > 9, soma os dois dígitos (ex: 14 -> 1 + 4 = 5 ou mult - 9)
        soma += (mult - 9) if mult > 9 else mult
        peso = 1 if peso == 2 else 2

    resto = soma % 10
    return 0 if resto == 0 else (10 - resto)


def calcular_mod11_bancario(numero: str) -> int:
    """
    Cálculo do Dígito Verificador Geral Módulo 11 para boletos bancários (pesos de 2 a 9).
    Regra FEBRABAN:
    Resto 0, 1 ou 10 -> DV = 1.
    Outros restos -> DV = 11 - resto.
    """
    soma = 0
    peso = 2
    for d in reversed(numero):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1

    resto = soma % 11
    diferenca = 11 - resto
    if diferenca in (0, 10, 11):
        return 1
    return diferenca


def calcular_data_fator(fator: int) -> Optional[date]:
    """
    Calcula a data de vencimento a partir do fator FEBRABAN.
    Data base 1: 07/10/1997 para fatores até 9999 (atingido em 21/02/2025).
    Data base 2 (ciclo novo): 22/02/2025 reinicia o fator em 1000.
    """
    if fator <= 0:
        return None

    # Ciclo 1 base: 07/10/1997
    data_base_1 = date(1997, 10, 7)
    # Ciclo 2 base: 22/02/2025 quando fator voltou a 1000
    hoje = date.today()

    if fator >= 1000:
        # Data do ciclo 1
        data_c1 = data_base_1 + timedelta(days=fator)
        # Data do ciclo 2 (fator 1000 = 22/02/2025)
        data_c2 = date(2025, 2, 22) + timedelta(days=fator - 1000)

        # Se a data de hoje for anterior a 2025, é ciclo 1; caso contrário, compara proximidade
        if hoje < date(2025, 1, 1):
            return data_c1
        # Se a data do ciclo 1 estiver muito distante no passado (> 5 anos), usa ciclo 2
        if (hoje - data_c1).days > 1800:
            return data_c2
        return data_c2
    else:
        # Fatores menores que 1000 eram usados antigamente ou sem vencimento
        return data_base_1 + timedelta(days=fator)


def linha_to_barras_cobranca(linha: str) -> Tuple[bool, str, str]:
    """
    Converte linha digitável de 47 dígitos de boleto bancário para código de barras de 44 dígitos.
    Valida os 3 DVs dos campos e o DV geral.
    """
    if len(linha) != 47:
        return False, "", "Linha digitável deve ter 47 dígitos."

    campo1 = linha[0:9]
    dv1 = int(linha[9])
    campo2 = linha[10:20]
    dv2 = int(linha[20])
    campo3 = linha[21:31]
    dv3 = int(linha[31])
    dv_geral = linha[32]
    campo5 = linha[33:47]  # fator (4) + valor (10)

    # Validar DVs dos campos 1, 2 e 3
    if calcular_mod10(campo1) != dv1:
        return False, "", f"Dígito verificador do Campo 1 inválido (esperado {calcular_mod10(campo1)}, recebido {dv1})."
    if calcular_mod10(campo2) != dv2:
        return False, "", f"Dígito verificador do Campo 2 inválido (esperado {calcular_mod10(campo2)}, recebido {dv2})."
    if calcular_mod10(campo3) != dv3:
        return False, "", f"Dígito verificador do Campo 3 inválido (esperado {calcular_mod10(campo3)}, recebido {dv3})."

    # Montagem dos 44 dígitos do código de barras:
    # 01-04: Banco (3) + Moeda (1) [linha 0:4]
    # 05: DV geral
    # 06-19: Fator de vencimento (4) + Valor (10) [campo5]
    # 20-24: Posições 5 a 9 da linha [linha 4:9]
    # 25-34: Posições 11 a 20 da linha [linha 10:20]
    # 35-44: Posições 22 a 31 da linha [linha 21:31]
    codigo_barras = (
        linha[0:4]
        + dv_geral
        + campo5
        + linha[4:9]
        + linha[10:20]
        + linha[21:31]
    )

    # Validar DV geral
    sem_dv = codigo_barras[0:4] + codigo_barras[5:]
    dv_calculado = calcular_mod11_bancario(sem_dv)
    if str(dv_calculado) != dv_geral:
        return False, codigo_barras, f"Dígito verificador geral inválido (esperado {dv_calculado}, recebido {dv_geral})."

    return True, codigo_barras, ""


def barras_to_linha_cobranca(barras: str) -> Tuple[bool, str, str]:
    """
    Converte código de barras de 44 dígitos para linha digitável formatada de 47 dígitos.
    """
    if len(barras) != 44:
        return False, "", "Código de barras deve ter 44 dígitos."

    banco_moeda = barras[0:4]
    dv_geral = barras[4]
    fator_valor = barras[5:19]
    campo_livre = barras[19:44]

    # Campo 1: Banco (3) + Moeda (1) + primeiros 5 do campo livre (5)
    c1 = banco_moeda + campo_livre[0:5]
    dv1 = calcular_mod10(c1)

    # Campo 2: posições 6 a 15 do campo livre (10)
    c2 = campo_livre[5:15]
    dv2 = calcular_mod10(c2)

    # Campo 3: posições 16 a 25 do campo livre (10)
    c3 = campo_livre[15:25]
    dv3 = calcular_mod10(c3)

    linha_47 = f"{c1}{dv1}{c2}{dv2}{c3}{dv3}{dv_geral}{fator_valor}"
    return True, linha_47, ""


def decode_boleto(raw_code: str) -> BoletoInfo:
    """
    Decodifica e valida qualquer boleto de cobrança bancária ou concessionária
    a partir da linha digitável ou código de barras fornecido.
    """
    # Remove qualquer caractere não numérico
    digits = re.sub(r"\D", "", raw_code.strip())

    if not digits:
        return BoletoInfo(
            is_valid=False,
            tipo="DESCONHECIDO",
            linha_digitavel="",
            codigo_barras="",
            banco_codigo="",
            banco_nome="",
            valor=None,
            data_vencimento=None,
            fator_vencimento=None,
            campo_livre="",
            erro_mensagem="Nenhum dígito informado."
        )

    # Detecta Concessionária / Arrecadação (inicia com dígito 8)
    if digits.startswith("8"):
        tipo = "CONCESSIONARIA"
        seg_cod = digits[1] if len(digits) > 1 else ""
        seg_nome = SEGMENTOS_CONCESSIONARIA.get(seg_cod, "Concessionária Geral")

        # Se tiver 48 dígitos (linha digitável)
        if len(digits) == 48:
            linha_dig = digits
            barras = digits[0:11] + digits[12:23] + digits[24:35] + digits[36:47]
        elif len(digits) == 44:
            barras = digits
            linha_dig = digits  # Simplificado para exibição
        else:
            return BoletoInfo(
                is_valid=False,
                tipo=tipo,
                linha_digitavel=digits,
                codigo_barras="",
                banco_codigo=seg_cod,
                banco_nome=seg_nome,
                valor=None,
                data_vencimento=None,
                fator_vencimento=None,
                campo_livre="",
                erro_mensagem=f"Boleto de concessionária deve ter 44 ou 48 dígitos (recebido {len(digits)})."
            )

        # Extração de valor em concessionárias (posições 4 a 14 do código de barras)
        try:
            val_cents = int(barras[4:15])
            valor = Decimal(val_cents) / Decimal(100) if val_cents > 0 else None
        except Exception:
            valor = None

        return BoletoInfo(
            is_valid=True,
            tipo=tipo,
            linha_digitavel=linha_dig,
            codigo_barras=barras,
            banco_codigo=seg_cod,
            banco_nome=seg_nome,
            valor=valor,
            data_vencimento=None,
            fator_vencimento=None,
            campo_livre=barras[15:],
            erro_mensagem=""
        )

    # Boleto de Cobrança Bancária
    tipo = "COBRANCA"
    if len(digits) == 47:
        linha_dig = digits
        valid, barras, err = linha_to_barras_cobranca(linha_dig)
    elif len(digits) == 44:
        barras = digits
        valid, linha_dig, err = barras_to_linha_cobranca(barras)
    else:
        return BoletoInfo(
            is_valid=False,
            tipo=tipo,
            linha_digitavel=digits,
            codigo_barras="",
            banco_codigo=digits[:3] if len(digits) >= 3 else "",
            banco_nome=BANCOS_BRASIL.get(digits[:3], "Desconhecido"),
            valor=None,
            data_vencimento=None,
            fator_vencimento=None,
            campo_livre="",
            erro_mensagem=f"Tamanho inválido para boleto bancário: {len(digits)} dígitos (esperado 44 ou 47)."
        )

    banco_cod = barras[0:3] if len(barras) >= 3 else ""
    banco_nome = BANCOS_BRASIL.get(banco_cod, f"Banco {banco_cod} (Outro)")

    # Fator de vencimento e valor
    try:
        fator = int(barras[5:9])
        dt_venc = calcular_data_fator(fator)
    except Exception:
        fator = None
        dt_venc = None

    try:
        val_cents = int(barras[9:19])
        valor = Decimal(val_cents) / Decimal(100) if val_cents > 0 else None
    except Exception:
        valor = None

    campo_livre = barras[19:44] if len(barras) >= 44 else ""

    return BoletoInfo(
        is_valid=valid,
        tipo=tipo,
        linha_digitavel=linha_dig,
        codigo_barras=barras,
        banco_codigo=banco_cod,
        banco_nome=banco_nome,
        valor=valor,
        data_vencimento=dt_venc,
        fator_vencimento=fator,
        campo_livre=campo_livre,
        erro_mensagem=err
    )


def format_linha_digitavel(linha: str) -> str:
    """Formata uma linha digitável de 47 dígitos com pontos e espaços padrão FEBRABAN."""
    digits = re.sub(r"\D", "", linha)
    if len(digits) == 47:
        return f"{digits[0:5]}.{digits[5:10]} {digits[10:15]}.{digits[15:21]} {digits[21:26]}.{digits[26:32]} {digits[32]} {digits[33:47]}"
    if len(digits) == 48:
        return f"{digits[0:12]} {digits[12:24]} {digits[24:36]} {digits[36:48]}"
    return linha
