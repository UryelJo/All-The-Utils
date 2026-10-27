"""
Lógica pura para conversão bidirecional entre arquivos físicos e Base64 / Data URI.
Suporta detecção de tipo MIME por extensão e magic bytes, sanitização e gravação segura.

Zero dependências de bibliotecas de interface gráfica.
"""
import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

MAGIC_MIMES = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # Substring/prefixo WEBP
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"\x1f\x8b\x08", "application/gzip"),
]


def detect_mime_type(file_path: Optional[Path] = None, data_sample: bytes = b"") -> str:
    """
    Detecta o tipo MIME inspecionando a extensão do arquivo e os bytes mágicos do início do arquivo.
    """
    if file_path:
        guessed, _ = mimetypes.guess_type(str(file_path))
        if guessed:
            return guessed

    for magic, mime in MAGIC_MIMES:
        if data_sample.startswith(magic):
            return mime

    # Fallback seguro
    return "application/octet-stream"


def file_to_base64(file_path: Path, include_data_uri: bool = True) -> Dict[str, Any]:
    """
    Converte um arquivo físico em Base64 e Data URI.
    Retorna metadados completos: tamanho, mime, hash preliminar e string.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    raw_bytes = path.read_bytes()
    file_size = len(raw_bytes)
    mime = detect_mime_type(path, raw_bytes[:32])

    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:{mime};base64,{b64_str}" if include_data_uri else ""

    return {
        "file_name": path.name,
        "file_size": file_size,
        "mime_type": mime,
        "base64_str": b64_str,
        "data_uri": data_uri,
        "char_count": len(b64_str),
    }


def parse_data_uri(raw_input: str) -> Tuple[bytes, Optional[str]]:
    """
    Interpreta uma string de entrada que pode ser um Data URI completo ou uma string Base64 pura.
    Retorna os bytes decodificados e o tipo MIME se detectado no cabeçalho Data URI.
    """
    cleaned = raw_input.strip()
    if not cleaned:
        raise ValueError("A entrada Base64 está vazia.")

    detected_mime: Optional[str] = None

    if cleaned.startswith("data:"):
        # Ex: data:image/png;base64,iVBORw0KGgoAAA...
        header_part, sep, payload = cleaned.partition(",")
        if not sep:
            raise ValueError("Data URI malformado: separador ',' ausente.")

        meta = header_part[5:]  # Remove "data:"
        parts = meta.split(";")
        detected_mime = parts[0] if parts and parts[0] else None
        # Remove quebras de linha e espaços do payload
        b64_content = "".join(payload.split())
    else:
        b64_content = "".join(cleaned.split())

    try:
        decoded_bytes = base64.b64decode(b64_content, validate=True)
    except Exception as exc:
        raise ValueError(f"Dados Base64 inválidos ou corrompidos: {exc}") from exc

    if not detected_mime and decoded_bytes:
        detected_mime = detect_mime_type(None, decoded_bytes[:32])

    return decoded_bytes, detected_mime


def base64_to_file(raw_input: str, output_path: Path) -> Dict[str, Any]:
    """
    Decodifica uma string Base64 ou Data URI e grava diretamente em um arquivo de destino.
    """
    decoded_bytes, detected_mime = parse_data_uri(raw_input)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(decoded_bytes)

    return {
        "output_path": str(out.resolve()),
        "file_size": len(decoded_bytes),
        "mime_type": detected_mime or "application/octet-stream",
    }
