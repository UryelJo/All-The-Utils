"""
Lógica pura para otimização e compressão de arquivos PDF.
Motor principal: pikepdf (qpdf) com recompressão das imagens internas via Pillow, que é onde
está o peso de PDFs escaneados. Reserva: pypdf (só recomprime fluxos de conteúdo).
"""
import io
import shutil
from pathlib import Path
from typing import Any, Dict
from pypdf import PdfReader, PdfWriter

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("pdf.compress")

MAX_IMAGE_SIDE = 2480       # ~A4 a 300 dpi: acima disso a imagem é reduzida
MIN_IMAGE_BYTES = 40_000    # imagens pequenas não compensam a recompressão


def _recompress_images(pdf, quality: int) -> int:
    """Recomprime em JPEG as imagens RGB/cinza de 8 bits que ficarem menores. Retorna quantas mudaram."""
    import pikepdf
    from PIL import Image

    changed = 0
    seen = set()
    for page in pdf.pages:
        # pikepdf 10+: get_images() também acha imagens dentro de form XObjects; .images foi depreciado
        images = page.get_images() if hasattr(page, "get_images") else page.images
        for _name, raw in images.items():
            if raw.objgen in seen:
                continue
            seen.add(raw.objgen)
            try:
                img = pikepdf.PdfImage(raw)
                filters = [str(f) for f in img.filters]
                if (img.bits_per_component != 8 or "/JPXDecode" in filters or "/JBIG2Decode" in filters
                        or str(img.colorspace) not in ("/DeviceRGB", "/DeviceGray") or img.image_mask
                        or len(raw.read_raw_bytes()) < MIN_IMAGE_BYTES):
                    continue
                pil = img.as_pil_image()
                if pil.mode not in ("RGB", "L"):
                    pil = pil.convert("RGB")
                if max(pil.size) > MAX_IMAGE_SIDE:
                    pil.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                if len(data) >= len(raw.read_raw_bytes()) * 0.9:
                    continue  # ganho irrelevante: mantém o original
                raw.write(data, filter=pikepdf.Name.DCTDecode)
                raw.Width, raw.Height = pil.size
                raw.ColorSpace = pikepdf.Name.DeviceGray if pil.mode == "L" else pikepdf.Name.DeviceRGB
                raw.BitsPerComponent = 8
                if "/DecodeParms" in raw:
                    del raw["/DecodeParms"]
                changed += 1
            except Exception:
                _log.debug("Imagem %s mantida sem recompressão", raw.objgen, exc_info=True)
    return changed


def _compress_with_pikepdf(src_path: Path, dst_path: Path, compress_streams: bool,
                           remove_metadata: bool, image_quality: int) -> int:
    import pikepdf

    with pikepdf.open(src_path) as pdf:
        images = _recompress_images(pdf, image_quality) if image_quality < 100 else 0
        if remove_metadata:
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                for key in list(meta.keys()):
                    del meta[key]
            if "/Info" in pdf.trailer:
                del pdf.trailer["/Info"]
        pdf.remove_unreferenced_resources()
        pdf.save(
            dst_path,
            compress_streams=compress_streams,
            recompress_flate=compress_streams,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
    return images


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

    images = 0
    try:
        images = _compress_with_pikepdf(src_path, dst_path, compress_streams, remove_metadata, image_quality)
        engine = "pikepdf"
    except ImportError:
        _compress_with_pypdf(src_path, dst_path, compress_streams, remove_metadata)
        engine = "pypdf"

    src_size = src_path.stat().st_size
    if dst_path.stat().st_size >= src_size:
        # Nunca devolve um arquivo maior que o original (PDF já otimizado)
        shutil.copy2(src_path, dst_path)
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
        "images_recompressed": images,
        "engine": engine,
    }


def _compress_with_pypdf(src_path: Path, dst_path: Path, compress_streams: bool, remove_metadata: bool) -> None:
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
            writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        except Exception:
            _log.debug("compress_identical_objects indisponível nesta versão do pypdf", exc_info=True)

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
