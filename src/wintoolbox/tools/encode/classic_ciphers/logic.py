"""
Lógica pura para codificação e decodificação de cifras clássicas da história da criptografia.

Cifras suportadas:
1. Cifra de César (deslocamento arbitrário e brute-force de todos os 25 alfabetos)
2. Cifra de Vigenère (polialfabética com palavra-chave)
3. Código Morse (padrão ITU internacional)
4. Cifra Atbash (inversão alfabética simétrica A <-> Z)
5. ROT13 e ROT47 (cifras de rotação simétricas / involuções)

Isolado de qualquer biblioteca de interface gráfica.
"""
from typing import Dict, List, Tuple


# Tabela internacional do Código Morse (ITU)
MORSE_CODE_DICT: Dict[str, str] = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    ";": "-.-.-.", "=": "-...-", "+": ".-.-.", "-": "-....-", "_": "..--.-",
    "\"": ".-..-.", "$": "...-..-", "@": ".--.-.",
}
REVERSE_MORSE_DICT: Dict[str, str] = {v: k for k, v in MORSE_CODE_DICT.items()}


def caesar_cipher(text: str, shift: int, decrypt: bool = False) -> str:
    """Aplica a Cifra de César com deslocamento arbitrário."""
    effective_shift = (-shift if decrypt else shift) % 26
    res = []
    for char in text:
        if "a" <= char <= "z":
            res.append(chr((ord(char) - ord("a") + effective_shift) % 26 + ord("a")))
        elif "A" <= char <= "Z":
            res.append(chr((ord(char) - ord("A") + effective_shift) % 26 + ord("A")))
        else:
            res.append(char)
    return "".join(res)


def caesar_brute_force(text: str) -> List[Tuple[int, str]]:
    """Gera todas as 25 rotações possíveis da Cifra de César para decifração."""
    return [(shift, caesar_cipher(text, shift, decrypt=True)) for shift in range(1, 26)]


def vigenere_cipher(text: str, key: str, decrypt: bool = False) -> str:
    """Aplica a Cifra de Vigenère baseada em palavra-chave."""
    clean_key = [c.upper() for c in key if c.isalpha()]
    if not clean_key:
        return text

    res = []
    key_idx = 0
    key_len = len(clean_key)

    for char in text:
        if char.isalpha():
            is_lower = char.islower()
            base = ord("a") if is_lower else ord("A")
            shift = ord(clean_key[key_idx % key_len]) - ord("A")
            if decrypt:
                shift = -shift
            new_char = chr((ord(char) - base + shift) % 26 + base)
            res.append(new_char)
            key_idx += 1
        else:
            res.append(char)

    return "".join(res)


def atbash_cipher(text: str) -> str:
    """Aplica a Cifra Atbash (inversão alfabética simétrica A <-> Z)."""
    res = []
    for char in text:
        if "a" <= char <= "z":
            res.append(chr(ord("z") - (ord(char) - ord("a"))))
        elif "A" <= char <= "Z":
            res.append(chr(ord("Z") - (ord(char) - ord("A"))))
        else:
            res.append(char)
    return "".join(res)


def text_to_morse(text: str) -> str:
    """Converte texto puro em Código Morse."""
    words = text.strip().split()
    morse_words = []
    for w in words:
        chars = []
        for c in w.upper():
            if c in MORSE_CODE_DICT:
                chars.append(MORSE_CODE_DICT[c])
        if chars:
            morse_words.append(" ".join(chars))
    return " / ".join(morse_words)


def morse_to_text(morse_code: str) -> str:
    """Converte Código Morse em texto alfanumérico."""
    words = morse_code.strip().split("/")
    decoded_words = []
    for w in words:
        letters = w.strip().split()
        dec_letters = [REVERSE_MORSE_DICT.get(l, "?") for l in letters if l]
        if dec_letters:
            decoded_words.append("".join(dec_letters))
    return " ".join(decoded_words)


def rot13_cipher(text: str) -> str:
    """Aplica a cifra de rotação 13 (alfabética)."""
    return caesar_cipher(text, 13)


def rot47_cipher(text: str) -> str:
    """
    Aplica a cifra ROT47 (rotaciona 47 posições nos caracteres ASCII visíveis de 33 '!' a 126 '~').
    Involução: aplicar duas vezes retorna o texto original.
    """
    res = []
    for char in text:
        code = ord(char)
        if 33 <= code <= 126:
            res.append(chr(33 + ((code + 14) % 94)))
        else:
            res.append(char)
    return "".join(res)
