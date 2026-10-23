"""
Lógica pura de compressão e otimização de imagens (Lossless, Lossy e Meta de Tamanho).
"""
import io
from pathlib import Path
from typing import Any, Dict, Tuple
from PIL import Image

COMPRESSION_MODES = [
    "Qualidade Visual Balanceada",
    "Otimização Sem Perdas (Lossless)",
    "Meta de Tamanho Máximo (KB)"
]

def compress_single_image(src: Path, dst: Path, params: Dict[str, Any]) -> Tuple[int, int]:
    """
    Comprime e otimiza uma imagem física de acordo com os parâmetros.
    Retorna (tamanho_anterior_bytes, tamanho_novo_bytes).
    """
    orig_size = src.stat().st_size
    mode = params.get("mode", "Qualidade Visual Balanceada")
    quality = params.get("quality", 80)
    target_kb = params.get("target_kb", 250)
    quantize_png = params.get("quantize_png", False)
    strip_exif = params.get("strip_exif", True)
    progressive_jpeg = params.get("progressive_jpeg", True)

    ext = (dst.suffix or src.suffix).lower()
    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        # Se strip_exif for True, descartamos o dicionário de info/exif
        save_kwargs = {}
        if not strip_exif and "exif" in im.info:
            save_kwargs["exif"] = im.info["exif"]

        # Otimização por Formato
        if ext in (".jpg", ".jpeg"):
            # JPEG não suporta RGBA
            if im.mode in ("RGBA", "LA", "P"):
                rgb = Image.new("RGB", im.size, (255, 255, 255))
                if im.mode == "RGBA":
                    rgb.paste(im, mask=im.split()[3])
                else:
                    rgb.paste(im.convert("RGB"))
                working_im = rgb
            else:
                working_im = im.copy()

            if mode == "Otimização Sem Perdas (Lossless)":
                working_im.save(dst, format="JPEG", quality=95, optimize=True, progressive=progressive_jpeg, **save_kwargs)
            elif mode == "Meta de Tamanho Máximo (KB)":
                target_bytes = target_kb * 1024
                # Busca binária de qualidade para chegar o mais perto possível do target_bytes
                low_q = 15
                high_q = 95
                best_buf = None

                for _ in range(6):
                    mid_q = (low_q + high_q) // 2
                    buf = io.BytesIO()
                    working_im.save(buf, format="JPEG", quality=mid_q, optimize=True, progressive=progressive_jpeg, **save_kwargs)
                    size = buf.tell()

                    if size <= target_bytes:
                        best_buf = buf.getvalue()
                        low_q = mid_q + 1
                    else:
                        high_q = mid_q - 1

                if best_buf:
                    dst.write_bytes(best_buf)
                else:
                    working_im.save(dst, format="JPEG", quality=20, optimize=True, **save_kwargs)
            else:
                # Qualidade balanceada
                working_im.save(dst, format="JPEG", quality=quality, optimize=True, progressive=progressive_jpeg, **save_kwargs)

        elif ext == ".png":
            working_im = im.copy()
            if quantize_png and working_im.mode != "P":
                # Reduz para 256 cores adaptativas (ótimo para ilustrações, gráficos, prints)
                working_im = working_im.quantize(colors=256, method=Image.Quantize.MEDIANCUT)

            working_im.save(dst, format="PNG", optimize=True, compress_level=9)

        elif ext == ".webp":
            working_im = im.copy()
            if mode == "Otimização Sem Perdas (Lossless)":
                working_im.save(dst, format="WEBP", lossless=True, **save_kwargs)
            elif mode == "Meta de Tamanho Máximo (KB)":
                target_bytes = target_kb * 1024
                low_q = 10
                high_q = 95
                best_buf = None

                for _ in range(6):
                    mid_q = (low_q + high_q) // 2
                    buf = io.BytesIO()
                    working_im.save(buf, format="WEBP", quality=mid_q, **save_kwargs)
                    size = buf.tell()
                    if size <= target_bytes:
                        best_buf = buf.getvalue()
                        low_q = mid_q + 1
                    else:
                        high_q = mid_q - 1

                if best_buf:
                    dst.write_bytes(best_buf)
                else:
                    working_im.save(dst, format="WEBP", quality=15, **save_kwargs)
            else:
                working_im.save(dst, format="WEBP", quality=quality, **save_kwargs)

        else:
            im.save(dst)

    new_size = dst.stat().st_size if dst.exists() else orig_size
    return (orig_size, new_size)
