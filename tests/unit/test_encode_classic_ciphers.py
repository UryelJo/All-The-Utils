"""
Testes unitários rigorosos para cifras clássicas de criptografia.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra (validação determinística exata).
"""
import pytest
from wintoolbox.tools.encode.classic_ciphers.logic import (
    atbash_cipher,
    caesar_brute_force,
    caesar_cipher,
    morse_to_text,
    rot13_cipher,
    rot47_cipher,
    text_to_morse,
    vigenere_cipher,
)


def test_caesar_cipher_deterministic():
    """Valida Cifra de César com shift clássico 3 e reversão."""
    original = "ABC XYZ abc xyz"
    encrypted = caesar_cipher(original, shift=3, decrypt=False)
    assert encrypted == "DEF ABC def abc"

    decrypted = caesar_cipher(encrypted, shift=3, decrypt=True)
    assert decrypted == original

    # Brute force deve conter a string original em uma das 25 posições
    rotations = caesar_brute_force(encrypted)
    assert len(rotations) == 25
    match_3 = [dec for shift, dec in rotations if shift == 3]
    assert match_3 == [original]


def test_vigenere_cipher_deterministic():
    """Valida Cifra de Vigenère polialfabética com vetor clássico."""
    msg = "ATTACKATDAWN"
    key = "LEMON"
    expected = "LXFOPVEFRNHR"

    enc = vigenere_cipher(msg, key, decrypt=False)
    assert enc == expected

    dec = vigenere_cipher(enc, key, decrypt=True)
    assert dec == msg


def test_morse_code_roundtrip():
    """Valida Código Morse padrão internacional ITU."""
    assert text_to_morse("SOS") == "... --- ..."
    assert morse_to_text("... --- ...") == "SOS"

    hello_morse = text_to_morse("HELLO WORLD")
    assert hello_morse == ".... . .-.. .-.. --- / .-- --- .-. .-.. -.."
    assert morse_to_text(hello_morse) == "HELLO WORLD"


def test_atbash_cipher():
    """Valida inversão simétrica do alfabeto na Cifra Atbash."""
    assert atbash_cipher("ABC") == "ZYX"
    assert atbash_cipher("abc") == "zyx"
    assert atbash_cipher("AZBY") == "ZAYB"
    # Duas aplicações consecutivas devem restaurar o original
    assert atbash_cipher(atbash_cipher("Mensagem Secreta")) == "Mensagem Secreta"


def test_rot13_and_rot47_involutions():
    """Valida que ROT13 e ROT47 são operações involutivas (f(f(x)) == x)."""
    text = "Hello, World! 123 @#$"

    rot13_1 = rot13_cipher(text)
    assert rot13_1 != text
    assert rot13_cipher(rot13_1) == text

    rot47_1 = rot47_cipher(text)
    assert rot47_1 != text
    assert rot47_cipher(rot47_1) == text
