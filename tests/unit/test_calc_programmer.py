"""
Testes unitários rigorosos para a Calculadora do Programador (calc.programmer).
"""
import pytest
from PySide6.QtWidgets import QApplication

from wintoolbox.tools.calc.programmer.logic import (
    bitwise_and,
    bitwise_not,
    bitwise_or,
    bitwise_rol,
    bitwise_ror,
    bitwise_sar,
    bitwise_shl,
    bitwise_shr,
    bitwise_xor,
    clamp_to_word,
    format_all_bases,
    format_binary,
    get_all_bits,
    get_bit,
    get_mask,
    parse_programmer_value,
    set_bit,
    to_signed,
    toggle_bit
)
from wintoolbox.tools.calc.programmer.tool import (
    ProgrammerCalculatorTool,
    ProgrammerCalculatorView
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_word_size_masks_and_signed_conversions():
    """Valida máscaras de bits e complemento de dois para tamanhos de palavra."""
    # 8 bits (BYTE)
    assert get_mask("BYTE") == 0xFF
    assert clamp_to_word(0x1FF, "BYTE") == 0xFF
    assert to_signed(0xFF, "BYTE") == -1
    assert to_signed(0x7F, "BYTE") == 127
    assert to_signed(0x80, "BYTE") == -128

    # 16 bits (WORD)
    assert get_mask("WORD") == 0xFFFF
    assert to_signed(0xFFFF, "WORD") == -1
    assert to_signed(0x8000, "WORD") == -32768

    # 32 bits (DWORD)
    assert get_mask("DWORD") == 0xFFFFFFFF
    assert to_signed(0xFFFFFFFF, "DWORD") == -1
    assert to_signed(0x7FFFFFFF, "DWORD") == 2147483647

    # 64 bits (QWORD)
    assert get_mask("QWORD") == 0xFFFFFFFFFFFFFFFF
    assert to_signed(0xFFFFFFFFFFFFFFFF, "QWORD") == -1


def test_parse_and_format_bases():
    """Valida parseamento de entradas numéricas e formatação entre todas as bases."""
    # Parsing com prefixos
    assert parse_programmer_value("0xFF", default_base=10, word_size="BYTE") == 255
    assert parse_programmer_value("0b1010", default_base=10, word_size="BYTE") == 10
    assert parse_programmer_value("0o77", default_base=10, word_size="BYTE") == 63
    assert parse_programmer_value("123", default_base=10, word_size="WORD") == 123
    assert parse_programmer_value("   0x1A   ", word_size="DWORD") == 26

    # Formatação completa em 8 bits
    res = format_all_bases(0x5A, "BYTE")
    assert res["hex"] == "5A"
    assert res["dec_unsigned"] == "90"
    assert res["dec_signed"] == "90"
    assert res["oct"] == "132"
    assert res["bin"] == "0101 1010"

    # Formatação binária de 16 bits agrupada em nibbles
    bin_fmt = format_binary(0xABCD, "WORD")
    assert bin_fmt == "1010 1011 1100 1101"


def test_bitwise_operations():
    """Valida operadores lógicos binários e deslocamentos."""
    # AND, OR, XOR, NOT
    assert bitwise_and(0b1100, 0b1010, "BYTE") == 0b1000
    assert bitwise_or(0b1100, 0b1010, "BYTE") == 0b1110
    assert bitwise_xor(0b1100, 0b1010, "BYTE") == 0b0110
    assert bitwise_not(0x00, "BYTE") == 0xFF
    assert bitwise_not(0xAA, "BYTE") == 0x55

    # Shifts Lógicos
    assert bitwise_shl(0x01, 4, "BYTE") == 0x10
    assert bitwise_shl(0x80, 1, "BYTE") == 0x00  # Trunca overflow
    assert bitwise_shr(0x10, 2, "BYTE") == 0x04

    # Shift Aritmético (preserva sinal)
    # 0x80 em 8 bits é -128. SAR 1 bit -> -64 (0xC0)
    assert bitwise_sar(0x80, 1, "BYTE") == 0xC0

    # Rotação circular (ROL e ROR)
    assert bitwise_rol(0x81, 1, "BYTE") == 0x03
    assert bitwise_ror(0x03, 1, "BYTE") == 0x81


def test_bit_manipulation():
    """Valida leitura, definição e inversão de bits individuais."""
    val = 0b00000000
    # Set bit 3
    val = set_bit(val, 3, 1, "BYTE")
    assert val == 0b00001000
    assert get_bit(val, 3) == 1
    assert get_bit(val, 2) == 0

    # Toggle bit 3
    val = toggle_bit(val, 3, "BYTE")
    assert val == 0
    assert get_bit(val, 3) == 0

    # Toggle bit 7 (MSB em BYTE)
    val = toggle_bit(val, 7, "BYTE")
    assert val == 0x80

    # Lista completa de bits
    bits = get_all_bits(0xA5, "BYTE")  # 10100101
    assert bits == [1, 0, 1, 0, 0, 1, 0, 1]


def test_programmer_calculator_view(qapp):
    """Valida interação visual, alternância de word size e operações na UI."""
    tool = ProgrammerCalculatorTool()
    view = ProgrammerCalculatorView(tool)

    # 1. Definir valor via texto Hexadecimal
    view.txt_hex.setText("FF")
    view._on_hex_edited("FF")

    assert view.txt_dec.text() == "255"
    assert "0000 0000 0000 0000 0000 0000 1111 1111" in view.txt_bin.text()

    # 2. Alternar para BYTE (8 bits)
    view.rb_byte.setChecked(True)
    assert view._word_size == "BYTE"
    assert view.txt_hex.text() == "FF"
    assert view.txt_bin.text() == "1111 1111"
    assert view.lbl_dec_signed.text() == "Com sinal: -1"

    # 3. Clicar no bit 0 para desativá-lo (1111 1110 = 0xFE)
    view._on_bit_clicked(0)
    assert view.txt_hex.text() == "FE"
    assert view.txt_dec.text() == "254"

    # 4. Operação bitwise via UI (AND com 0xF0 -> resultado deve ser 0xF0)
    idx_and = view.combo_op.findData("AND")
    assert idx_and >= 0
    view.combo_op.setCurrentIndex(idx_and)
    view.txt_operand.setText("0xF0")
    view._apply_bitwise_op()

    assert view.txt_hex.text() == "F0"
    assert view.txt_dec.text() == "240"

    # 5. Botão Zerar
    view._clear_all()
    assert view.txt_hex.text() == "00"
    assert view.txt_dec.text() == "0"
