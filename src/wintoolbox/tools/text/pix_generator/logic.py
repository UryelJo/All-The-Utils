"""
Lógica pura de geração de Pix Copia e Cola (BR Code) conforme a especificação do Banco Central do Brasil / EMVCo.
Inclui o algoritmo exato de CRC16-CCITT (Polinômio 0x1021).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import re
from typing import Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("text.pix_generator")


def _format_tlv(tag: str, value: str) -> str:
    """Formata um campo no padrão TLV: Tag (2 dígitos) + Comprimento (2 dígitos) + Valor."""
    length = f"{len(value):02d}"
    return f"{tag}{length}{value}"


def compute_crc16(payload: str) -> str:
    """
    Calcula o checksum CRC16-CCITT (0xFFFF, polinômio 0x1021)
    conforme exigido pelo Banco Central para o BR Code.
    """
    crc = 0xFFFF
    polynomial = 0x1021

    for byte in payload.encode("utf-8"):
        crc ^= (byte << 8)
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc = ((crc << 1) ^ polynomial) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF

    return f"{crc:04X}"


def normalize_string(text: str, max_len: int) -> str:
    """Remove caracteres especiais e trunca o texto para caber no padrão EMV."""
    # Substitui acentos comuns
    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a", "é": "e", "ê": "e",
        "í": "i", "ó": "o", "õ": "o", "ô": "o", "ú": "u", "ç": "c",
        "Á": "A", "À": "A", "Ã": "A", "Â": "A", "É": "E", "Ê": "E",
        "Í": "I", "Ó": "O", "Õ": "O", "Ô": "O", "Ú": "U", "Ç": "C"
    }
    clean = text
    for orig, rep in replacements.items():
        clean = clean.replace(orig, rep)

    clean = re.sub(r"[^a-zA-Z0-9\s]", "", clean).strip()
    return clean[:max_len]


def generate_pix_payload(
    pix_key: str,
    merchant_name: str,
    merchant_city: str,
    amount: Optional[float] = None,
    txid: str = "***",
    description: str = ""
) -> str:
    """
    Gera a string completa do Pix Copia e Cola / BR Code estático.
    - pix_key: Chave Pix (E-mail, CPF, CNPJ, Celular +55... ou EVP)
    - merchant_name: Nome do recebedor (até 25 caracteres)
    - merchant_city: Cidade do recebedor (até 15 caracteres)
    - amount: Valor opcional em Reais (ex: 50.00)
    - txid: Identificador da transação (padrão '***' para sem ID)
    """
    key_clean = pix_key.strip()
    if not key_clean:
        raise ValueError("A chave Pix não pode estar vazia.")

    name_clean = normalize_string(merchant_name, 25) or "RECEBEDOR PIX"
    city_clean = normalize_string(merchant_city, 15) or "BRASIL"
    txid_clean = normalize_string(txid, 25) or "***"

    # 00: Payload Format Indicator
    pfi = _format_tlv("00", "01")

    # 26: Merchant Account Information
    mai_gui = _format_tlv("00", "br.gov.bcb.pix")
    mai_key = _format_tlv("01", key_clean)
    mai_desc = _format_tlv("02", normalize_string(description, 40)) if description else ""
    mai = _format_tlv("26", f"{mai_gui}{mai_key}{mai_desc}")

    # 52: Merchant Category Code (0000 padrão)
    mcc = _format_tlv("52", "0000")

    # 53: Transaction Currency (986 = BRL)
    curr = _format_tlv("53", "986")

    # 54: Transaction Amount (opcional)
    amt_tlv = ""
    if amount is not None and amount > 0:
        amt_tlv = _format_tlv("54", f"{amount:.2f}")

    # 58: Country Code (BR)
    country = _format_tlv("58", "BR")

    # 59: Merchant Name
    m_name = _format_tlv("59", name_clean)

    # 60: Merchant City
    m_city = _format_tlv("60", city_clean)

    # 62: Additional Data Field (TXID)
    adf_txid = _format_tlv("05", txid_clean)
    adf = _format_tlv("62", adf_txid)

    # Monta payload antes do CRC
    raw_payload = f"{pfi}{mai}{mcc}{curr}{amt_tlv}{country}{m_name}{m_city}{adf}6304"

    # Calcula e anexa CRC16
    crc = compute_crc16(raw_payload)
    return f"{raw_payload}{crc}"
