"""
Lógica pura para detecção de tipo real de arquivos via assinaturas binárias (Magic Bytes).
Detecta divergências entre extensão declarada e tipo real, identificando arquivos mascarados.

Zero dependências de interface gráfica ou widgets.
"""
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple


MAGIC_SIGNATURES: List[Dict[str, Any]] = [
    # Imagens
    {"name": "PNG Image", "mime": "image/png", "ext": ".png", "magic": b"\x89PNG\r\n\x1a\n", "offset": 0},
    {"name": "JPEG Image", "mime": "image/jpeg", "ext": ".jpg", "magic": b"\xff\xd8\xff", "offset": 0},
    {"name": "GIF87a Image", "mime": "image/gif", "ext": ".gif", "magic": b"GIF87a", "offset": 0},
    {"name": "GIF89a Image", "mime": "image/gif", "ext": ".gif", "magic": b"GIF89a", "offset": 0},
    {"name": "BMP Image", "mime": "image/bmp", "ext": ".bmp", "magic": b"BM", "offset": 0},
    {"name": "Windows Icon", "mime": "image/x-icon", "ext": ".ico", "magic": b"\x00\x00\x01\x00", "offset": 0},
    {"name": "TIFF (Little Endian)", "mime": "image/tiff", "ext": ".tiff", "magic": b"II*\x00", "offset": 0},
    {"name": "TIFF (Big Endian)", "mime": "image/tiff", "ext": ".tiff", "magic": b"MM\x00*", "offset": 0},

    # Documentos e Compactação
    {"name": "PDF Document", "mime": "application/pdf", "ext": ".pdf", "magic": b"%PDF-", "offset": 0},
    {"name": "ZIP Archive / Office Open XML", "mime": "application/zip", "ext": ".zip", "magic": b"PK\x03\x04", "offset": 0},
    {"name": "7-Zip Archive", "mime": "application/x-7z-compressed", "ext": ".7z", "magic": b"7z\xbc\xaf\x27\x1c", "offset": 0},
    {"name": "RAR Archive", "mime": "application/x-rar-compressed", "ext": ".rar", "magic": b"Rar!\x1a\x07", "offset": 0},
    {"name": "GZIP Compressed", "mime": "application/gzip", "ext": ".gz", "magic": b"\x1f\x8b", "offset": 0},
    {"name": "BZIP2 Compressed", "mime": "application/x-bzip2", "ext": ".bz2", "magic": b"BZh", "offset": 0},

    # Executáveis
    {"name": "Windows Executable (PE / MZ)", "mime": "application/x-dosexec", "ext": ".exe", "magic": b"MZ", "offset": 0},
    {"name": "Linux ELF Binary", "mime": "application/x-executable", "ext": ".elf", "magic": b"\x7fELF", "offset": 0},

    # Áudio / Vídeo
    {"name": "ID3v2 MP3 Audio", "mime": "audio/mpeg", "ext": ".mp3", "magic": b"ID3", "offset": 0},
    {"name": "OGG Container", "mime": "audio/ogg", "ext": ".ogg", "magic": b"OggS", "offset": 0},
    {"name": "FLAC Audio", "mime": "audio/flac", "ext": ".flac", "magic": b"fLaC", "offset": 0},
    {"name": "Matroska / WebM Video", "mime": "video/x-matroska", "ext": ".mkv", "magic": b"\x1a\x45\xdf\xa3", "offset": 0},

    # Outros
    {"name": "SQLite Database", "mime": "application/vnd.sqlite3", "ext": ".sqlite", "magic": b"SQLite format 3\x00", "offset": 0},
]


def detect_file_type(file_path: str) -> Dict[str, Any]:
    """
    Inspeciona os bytes iniciais de um arquivo para determinar seu tipo real e se há divergência com a extensão declarada.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    declared_ext = p.suffix.lower()
    file_size = p.stat().st_size

    if file_size == 0:
        return {
            "file_path": file_path,
            "file_name": p.name,
            "file_size": 0,
            "declared_ext": declared_ext,
            "real_type": "Arquivo Vazio (0 byte)",
            "recommended_ext": declared_ext or ".txt",
            "mime_type": "application/x-empty",
            "is_mismatch": False,
            "magic_hex": "",
        }

    # Lê cabeçalho de até 512 bytes
    header = b""
    with open(file_path, "rb") as f:
        header = f.read(512)

    magic_hex = header[:16].hex(" ").upper()

    # Verifica assinaturas padrão
    matched = None
    for sig in MAGIC_SIGNATURES:
        offset = sig["offset"]
        magic = sig["magic"]
        if len(header) >= offset + len(magic):
            if header[offset:offset + len(magic)] == magic:
                matched = sig
                break

    # Detecções especiais: RIFF (WAV vs WebP vs AVI)
    if not matched and header.startswith(b"RIFF") and len(header) >= 12:
        sub_type = header[8:12]
        if sub_type == b"WEBP":
            matched = {"name": "WebP Image", "mime": "image/webp", "ext": ".webp"}
        elif sub_type == b"WAVE":
            matched = {"name": "WAV Audio", "mime": "audio/wav", "ext": ".wav"}
        elif sub_type == b"AVI ":
            matched = {"name": "AVI Video", "mime": "video/x-msvideo", "ext": ".avi"}

    # MP4 / QuickTime (ftyp no offset 4)
    if not matched and len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12].decode("ascii", errors="replace").strip()
        matched = {"name": f"MP4/QuickTime Video ({brand})", "mime": "video/mp4", "ext": ".mp4"}

    # Texto Puro / UTF-8
    if not matched:
        is_text = False
        try:
            sample_txt = header.decode("utf-8")
            if all(c.isprintable() or c in ("\r", "\n", "\t") for c in sample_txt):
                is_text = True
        except UnicodeDecodeError:
            pass

        if is_text:
            cleaned = sample_txt.strip()
            if cleaned.startswith("<?xml") or cleaned.startswith("<html"):
                matched = {"name": "XML / HTML Document", "mime": "text/xml", "ext": ".xml"}
            elif (cleaned.startswith("{") and "}" in cleaned) or (cleaned.startswith("[") and "]" in cleaned):
                matched = {"name": "JSON Document", "mime": "application/json", "ext": ".json"}
            else:
                matched = {"name": "Texto Puro (UTF-8 / ASCII)", "mime": "text/plain", "ext": ".txt"}

    # Resultado padrão para desconhecido
    if not matched:
        return {
            "file_path": file_path,
            "file_name": p.name,
            "file_size": file_size,
            "declared_ext": declared_ext,
            "real_type": "Binário Desconhecido / Genérico",
            "recommended_ext": declared_ext,
            "mime_type": "application/octet-stream",
            "is_mismatch": False,
            "magic_hex": magic_hex,
        }

    real_type = matched["name"]
    recommended_ext = matched["ext"]
    mime_type = matched["mime"]

    # Validação de divergência
    # Office Open XML (.docx, .xlsx, .pptx, .jar) usam internamente estrutura ZIP
    valid_zip_extensions = {".zip", ".docx", ".xlsx", ".pptx", ".jar", ".apk", ".cbz"}
    if recommended_ext == ".zip" and declared_ext in valid_zip_extensions:
        is_mismatch = False
    elif recommended_ext == ".jpg" and declared_ext in {".jpg", ".jpeg"}:
        is_mismatch = False
    elif recommended_ext == ".tiff" and declared_ext in {".tif", ".tiff"}:
        is_mismatch = False
    else:
        is_mismatch = declared_ext != recommended_ext

    return {
        "file_path": file_path,
        "file_name": p.name,
        "file_size": file_size,
        "declared_ext": declared_ext,
        "real_type": real_type,
        "recommended_ext": recommended_ext,
        "mime_type": mime_type,
        "is_mismatch": is_mismatch,
        "magic_hex": magic_hex,
    }


def correct_file_extension(
    file_path: str,
    recommended_ext: str,
    output_dir: str,
) -> str:
    """
    Copia o arquivo para a pasta de saída com a extensão corrigida.
    """
    src_p = Path(file_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clean_ext = recommended_ext if recommended_ext.startswith(".") else f".{recommended_ext}"
    target_name = f"{src_p.stem}{clean_ext}"
    target_path = out_dir / target_name

    shutil.copy2(file_path, target_path)
    return str(target_path)
