"""
Lógica pura da ferramenta Codificador e Decodificador Universal.
Codifica e decodifica textos em Base64, URL, HTML, Hexadecimal, Unicode Escape e ROT13.
"""
import base64
import codecs
import html
from typing import List
import urllib.parse

SUPPORTED_ENCODINGS: List[str] = [
    "Base64",
    "URL Encode",
    "HTML Entities",
    "Hexadecimal",
    "Unicode Escape",
    "ROT13",
]


def encode_text(text: str, format_name: str) -> str:
    """Codifica o texto de acordo com o formato escolhido."""
    if format_name == "Base64":
        return base64.b64encode(text.encode("utf-8")).decode("utf-8")
    elif format_name == "URL Encode":
        return urllib.parse.quote(text)
    elif format_name == "HTML Entities":
        return html.escape(text)
    elif format_name == "Hexadecimal":
        return text.encode("utf-8").hex(" ")
    elif format_name == "Unicode Escape":
        return text.encode("unicode_escape").decode("utf-8")
    elif format_name == "ROT13":
        return codecs.encode(text, "rot_13")
    return text


def decode_text(text: str, format_name: str) -> str:
    """Decodifica o texto de acordo com o formato escolhido."""
    if format_name == "Base64":
        cleaned = "".join(text.split())
        missing_padding = len(cleaned) % 4
        if missing_padding:
            cleaned += "=" * (4 - missing_padding)
        return base64.b64decode(cleaned.encode("utf-8")).decode("utf-8", errors="replace")
    elif format_name == "URL Encode":
        return urllib.parse.unquote(text)
    elif format_name == "HTML Entities":
        return html.unescape(text)
    elif format_name == "Hexadecimal":
        cleaned = text.replace(" ", "").replace("0x", "")
        return bytes.fromhex(cleaned).decode("utf-8", errors="replace")
    elif format_name == "Unicode Escape":
        return codecs.decode(text.encode("utf-8"), "unicode_escape")
    elif format_name == "ROT13":
        return codecs.decode(text, "rot_13")
    return text
