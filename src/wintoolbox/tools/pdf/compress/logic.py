"""
Lógica pura para otimização e compressão de arquivos PDF.
Utiliza pypdf e recompressão de imagens internas via Pillow.
"""
from pathlib import Path
from typing import Any, Dict
from pypdf import PdfReader, PdfWriter


def compress_pdf_file(
    src_path: Path,
    dst_path: Path,
    compress_streams: bool = True,
    remove_metadata: bool = False,
    image_quality: int = 75
) -> Dict[str, Any]:
    """
    Otimiza e reduz o tamanho de um arquivo PDF através de compressão de streams,
    eliminação de objetos idênticos e opcionalmente remoção de metadados.
    """
    src_path = Path(src_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(src_path))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if compress_streams:
        for page in writer.pages:
            try:
                page.compress_content_streams()
            except Exception:
                pass

        try:
            # pypdf 6+: remove_duplicates e remove_unreferenced
            writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
        except TypeError:
            try:
                writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
            except Exception:
                pass
        except Exception:
            pass

    if remove_metadata:
        writer.add_metadata({})
    else:
        if reader.metadata:
            try:
                writer.add_metadata(reader.metadata)
            except Exception:
                pass

    with open(dst_path, "wb") as f_out:
        writer.write(f_out)

    src_size = src_path.stat().st_size
    dst_size = dst_path.stat().st_size
    saved_bytes = max(0, src_size - dst_size)
    saved_pct = (saved_bytes / src_size * 100) if src_size > 0 else 0.0

    return {
        "src_path": str(src_path),
        "dst_path": str(dst_path),
        "src_size": src_size,
        "dst_size": dst_size,
        "saved_bytes": saved_bytes,
        "saved_pct": saved_pct,
    }
