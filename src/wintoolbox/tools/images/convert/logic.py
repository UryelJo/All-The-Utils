"""
Lógica pura de conversão universal de imagens usando Pillow, pillow-heif e LittleCMS2 (ImageCms).
Suporta formato Apple iPhone HEIF/HEIC (.heic/.heif/.hif) bidirecional, conversão colorimétrica
Display P3 -> sRGB, controle seletivo de metadados EXIF/GPS, modo Lossless, subsampling de croma
e 18 formatos de saída, totalmente independente de interface gráfica (UI).
"""
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageCms, ImageOps

_HEIF_REGISTERED: bool = False


def ensure_heif_registered() -> bool:
    """Garante de forma idempotente que o codec HEIF/HEIC esteja registrado no Pillow (inclusive em subprocessos)."""
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return True
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        _HEIF_REGISTERED = True
        return True
    except ImportError:
        return False


ensure_heif_registered()

# 42 extensões de imagem compatíveis para leitura em lote
SUPPORTED_IMAGE_INPUTS: List[str] = [
    # Formatos populares, Web e Desktop
    ".png", ".apng", ".jpg", ".jpeg", ".jpe", ".jfif", ".webp", ".gif",
    ".bmp", ".dib", ".tif", ".tiff", ".ico", ".cur",
    # Apple iPhone (HEIF/HEIC), Câmeras Digitais (HIF/MPO) e AV1 (AVIF)
    ".heic", ".heif", ".heics", ".heifs", ".hif", ".avif", ".avifs", ".mpo",
    # Design (Photoshop), Jogos/3D (TGA/DDS), Modernos (QOI), macOS (ICNS) e Técnicos (JPEG2000/Netpbm)
    ".psd", ".qoi", ".tga", ".dds", ".icns",
    ".jp2", ".j2k", ".jpx", ".jpf", ".j2c",
    ".ppm", ".pgm", ".pbm", ".pnm", ".pcx", ".pfm", ".sgi", ".ras", ".xbm", ".xpm",
]

# 18 formatos de saída suportados
SUPPORTED_OUTPUTS: List[str] = [
    "WEBP",
    "JPG",
    "PNG",
    "HEIC",
    "HEIF",
    "AVIF",
    "TIFF",
    "BMP",
    "GIF",
    "ICO",
    "ICNS",
    "QOI",
    "TGA",
    "DDS",
    "JP2",
    "PPM",
    "PCX",
    "PDF",
]

PILLOW_FORMAT_MAP: Dict[str, str] = {
    "WEBP": "WEBP",
    "JPG": "JPEG",
    "JPEG": "JPEG",
    "PNG": "PNG",
    "HEIC": "HEIF",
    "HEIF": "HEIF",
    "AVIF": "AVIF",
    "TIFF": "TIFF",
    "TIF": "TIFF",
    "BMP": "BMP",
    "GIF": "GIF",
    "ICO": "ICO",
    "ICNS": "ICNS",
    "QOI": "QOI",
    "TGA": "TGA",
    "DDS": "DDS",
    "JP2": "JPEG2000",
    "JPEG2000": "JPEG2000",
    "PPM": "PPM",
    "PCX": "PCX",
    "PDF": "PDF",
}

OUTPUT_EXTENSION_MAP: Dict[str, str] = {
    "WEBP": ".webp",
    "JPG": ".jpg",
    "JPEG": ".jpg",
    "PNG": ".png",
    "HEIC": ".heic",
    "HEIF": ".heif",
    "AVIF": ".avif",
    "TIFF": ".tiff",
    "TIF": ".tiff",
    "BMP": ".bmp",
    "GIF": ".gif",
    "ICO": ".ico",
    "ICNS": ".icns",
    "QOI": ".qoi",
    "TGA": ".tga",
    "DDS": ".dds",
    "JP2": ".jp2",
    "JPEG2000": ".jp2",
    "PPM": ".ppm",
    "PCX": ".pcx",
    "PDF": ".pdf",
}

LOSSY_CAPABLE_FORMATS = {"JPG", "JPEG", "WEBP", "HEIC", "HEIF", "AVIF"}
LOSSLESS_TOGGLE_FORMATS = {"WEBP", "HEIC", "HEIF", "AVIF"}
SUBSAMPLING_CAPABLE_FORMATS = {"JPG", "JPEG", "HEIC", "HEIF"}
NO_ALPHA_FORMATS = {"JPEG", "PDF", "PPM", "PCX", "BMP"}
EXIF_CAPABLE_PILLOW_FORMATS = {"JPEG", "WEBP", "HEIF", "AVIF", "PNG", "TIFF"}
ICC_CAPABLE_PILLOW_FORMATS = {"JPEG", "WEBP", "HEIF", "AVIF", "PNG", "TIFF"}

ICNS_VALID_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def get_output_extension(target_format: str) -> str:
    """Retorna a extensão de arquivo canônica (com ponto) para o formato informado."""
    key = target_format.strip().upper().lstrip(".")
    if key not in OUTPUT_EXTENSION_MAP:
        raise ValueError(f"Formato de saída de imagem não suportado: '{target_format}'")
    return OUTPUT_EXTENSION_MAP[key]


def parse_bg_color(bg_color: Union[str, Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """Valida e converte uma cor RGB em tupla ou string hexadecimal (#RRGGBB / #RGB) para (R, G, B)."""
    if isinstance(bg_color, tuple) and len(bg_color) >= 3:
        return (
            max(0, min(255, int(bg_color[0]))),
            max(0, min(255, int(bg_color[1]))),
            max(0, min(255, int(bg_color[2]))),
        )
    if isinstance(bg_color, str):
        raw = bg_color.strip().lstrip("#")
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        if len(raw) == 6:
            try:
                return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
            except ValueError as exc:
                raise ValueError(f"Cor hexadecimal inválida: '{bg_color}'") from exc
    raise ValueError(f"Formato de cor de fundo inválido: '{bg_color}'")


def _apply_color_profile(
    img: Image.Image,
    raw_icc: Optional[bytes],
    color_profile_mode: str,
    target_supports_icc: bool,
) -> Tuple[Image.Image, Optional[bytes]]:
    """
    Gerencia perfis de cor ICC (ex: Apple Display P3 de fotos iPhone HEIC -> sRGB).
    Modos:
      - 'srgb': converte espaços wide-gamut (Display P3, AdobeRGB, CMYK) para sRGB padrão.
      - 'preserve': mantém o perfil ICC original sem alterar os valores dos pixels.
      - 'strip': descarta qualquer perfil ICC embutido.
    """
    mode = (color_profile_mode or "srgb").strip().lower()
    if mode == "strip":
        return img, None
    if mode == "preserve":
        return img, (raw_icc if target_supports_icc else None)

    if not raw_icc:
        return img, None

    try:
        src_prof = ImageCms.ImageCmsProfile(io.BytesIO(raw_icc))
        srgb_core = ImageCms.createProfile("sRGB")
        srgb_prof = ImageCms.ImageCmsProfile(srgb_core)
        srgb_bytes = srgb_prof.tobytes() if target_supports_icc else None

        desc = (ImageCms.getProfileDescription(src_prof) or "").strip().lower()
        if "srgb" in desc and "p3" not in desc and "adobe" not in desc:
            return img, srgb_bytes

        if img.mode == "RGBA":
            alpha = img.getchannel("A")
            rgb = img.convert("RGB")
            converted_rgb = ImageCms.profileToProfile(
                rgb,
                src_prof,
                srgb_prof,
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
                outputMode="RGB",
            )
            if converted_rgb is not None:
                converted_rgba = converted_rgb.convert("RGBA")
                converted_rgba.putalpha(alpha)
                return converted_rgba, srgb_bytes
        elif img.mode in ("RGB", "CMYK"):
            converted = ImageCms.profileToProfile(
                img,
                src_prof,
                srgb_prof,
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
                outputMode="RGB",
            )
            if converted is not None:
                return converted, srgb_bytes
    except Exception:
        # Se o perfil ICC embutido estiver corrompido, não interrompe a conversão da imagem
        return img, (raw_icc if (mode == "preserve" and target_supports_icc) else None)

    return img, (raw_icc if target_supports_icc else None)


def _build_exif_bytes(opened: Image.Image, exif_mode: str) -> Optional[bytes]:
    """
    Extrai e filtra os metadados EXIF conforme a política escolhida:
      - 'preserve': mantém EXIF completo ajustando Orientation=1 (pós exif_transpose).
      - 'strip_gps': mantém data/câmera mas remove completamente coordenadas GPS (0x8825).
      - 'strip_all': remove todos os metadados EXIF.
    """
    mode = (exif_mode or "preserve").strip().lower()
    if mode == "strip_all":
        return None

    try:
        exif = opened.getexif()
        if not exif:
            return None

        # Como os pixels já são transpostos fisicamente com exif_transpose, evita dupla rotação
        if 0x0112 in exif:
            exif[0x0112] = 1

        if mode == "strip_gps":
            if 0x8825 in exif:
                del exif[0x8825]
            if hasattr(exif, "_ifds") and 0x8825 in exif._ifds:
                del exif._ifds[0x8825]

        return exif.tobytes() if len(exif) > 0 else None
    except Exception:
        return None


def _normalize_high_bit_or_float(img: Image.Image) -> Image.Image:
    """Normaliza modos float/32-bit (ex: .pfm, .tiff científico) para 8-bit compatível."""
    if img.mode in ("F", "I", "I;16", "I;16L", "I;16B"):
        try:
            extrema = img.getextrema()
            if isinstance(extrema, tuple) and len(extrema) == 2:
                lo, hi = float(extrema[0]), float(extrema[1])
                span = (hi - lo) if hi > lo else 1.0
                return img.point(lambda v: max(0, min(255, int(((float(v) - lo) / span) * 255.0))), mode="L")
        except Exception:
            pass
        return img.convert("L")
    return img


def _fit_square_rgba(img: Image.Image, target_side: int) -> Image.Image:
    """Encaixa uma imagem proporcionalmente em um canvas quadrado RGBA transparente."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    if w == target_side and h == target_side:
        return rgba
    ratio = min(target_side / max(1, w), target_side / max(1, h))
    new_w = max(1, int(round(w * ratio)))
    new_h = max(1, int(round(h * ratio)))
    resized = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_side, target_side), (0, 0, 0, 0))
    canvas.paste(resized, ((target_side - new_w) // 2, (target_side - new_h) // 2))
    return canvas


def _prepare_image_mode(
    img: Image.Image,
    pillow_format: str,
    bg_rgb: Tuple[int, int, int],
) -> Image.Image:
    """Adapta canais, transparência e geometria para os requisitos do formato de destino."""
    if pillow_format not in ("TIFF", "PNG"):
        img = _normalize_high_bit_or_float(img)
    elif img.mode == "F":
        img = _normalize_high_bit_or_float(img)

    has_alpha = (
        img.mode in ("RGBA", "LA", "PA")
        or (img.mode == "P" and "transparency" in img.info)
    )

    if pillow_format in NO_ALPHA_FORMATS:
        if has_alpha:
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, bg_rgb)
            bg.paste(rgba, mask=rgba.getchannel("A"))
            return bg
        if img.mode != "RGB":
            return img.convert("RGB")
        return img

    if pillow_format == "ICNS":
        max_dim = max(img.size)
        chosen = 512
        for candidate in ICNS_VALID_SIZES:
            if candidate >= max_dim:
                chosen = candidate
                break
        else:
            chosen = 1024
        chosen = max(64, chosen)
        return _fit_square_rgba(img, chosen)

    if pillow_format == "ICO":
        w, h = img.size
        side = min(256, max(16, max(w, h)))
        if w != h or max(w, h) > 256:
            return _fit_square_rgba(img, side)
        return img.convert("RGBA")

    if pillow_format == "DDS":
        return img.convert("RGBA")

    if pillow_format == "GIF":
        if has_alpha:
            return img.convert("RGBA")
        return img.convert("RGB")

    # Formatos com suporte nativo a transparência (PNG, WEBP, HEIF/HEIC, AVIF, QOI, TGA, TIFF, JPEG2000)
    if has_alpha:
        return img.convert("RGBA")
    if pillow_format in ("HEIF", "AVIF", "WEBP", "QOI"):
        return img.convert("RGB")
    if img.mode not in ("RGB", "RGBA", "L", "I;16"):
        return img.convert("RGB")
    if pillow_format == "JPEG2000" and img.mode == "I;16":
        return _normalize_high_bit_or_float(img).convert("RGB")
    return img


def _build_save_kwargs(
    pillow_format: str,
    quality: int,
    lossless: bool,
    subsampling: str,
    exif_bytes: Optional[bytes],
    icc_bytes: Optional[bytes],
) -> Dict[str, Any]:
    """Constrói os argumentos ótimos do encoder do Pillow / pillow-heif."""
    kwargs: Dict[str, Any] = {}
    clamped_q = max(10, min(100, int(quality)))
    sub_norm = (subsampling or "4:2:0").strip()

    if pillow_format == "JPEG":
        kwargs["quality"] = clamped_q
        kwargs["optimize"] = True
        sub_map = {"4:4:4": 0, "4:2:2": 1, "4:2:0": 2}
        if sub_norm in sub_map:
            kwargs["subsampling"] = sub_map[sub_norm]

    elif pillow_format == "WEBP":
        if lossless:
            kwargs["lossless"] = True
            kwargs["quality"] = 100
        else:
            kwargs["quality"] = clamped_q

    elif pillow_format == "HEIF":
        if lossless:
            kwargs["quality"] = -1
            kwargs["chroma"] = 444
            kwargs["matrix_coefficients"] = 0
        else:
            kwargs["quality"] = clamped_q
            chroma_map = {"4:4:4": 444, "4:2:2": 422}
            if sub_norm in chroma_map:
                kwargs["chroma"] = chroma_map[sub_norm]

    elif pillow_format == "AVIF":
        kwargs["quality"] = 100 if lossless else clamped_q
        if lossless or sub_norm == "4:4:4":
            kwargs["subsampling"] = "4:4:4"

    elif pillow_format == "PNG":
        kwargs["optimize"] = True

    elif pillow_format == "ICO":
        kwargs["sizes"] = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    if exif_bytes and pillow_format in EXIF_CAPABLE_PILLOW_FORMATS:
        kwargs["exif"] = exif_bytes

    if icc_bytes and pillow_format in ICC_CAPABLE_PILLOW_FORMATS:
        kwargs["icc_profile"] = icc_bytes

    return kwargs


def _clean_frame_stem(output_path: Path) -> str:
    """Extrai o nome base limpo mesmo quando output_path é um temporário atômico (.wtbx-...)."""
    stem = output_path.stem
    if ".wtbx-" in stem:
        return stem.split(".wtbx-")[0]
    return stem


def convert_single_image(
    source_path: Path,
    output_path: Path,
    target_format: str = "WEBP",
    quality: int = 90,
    lossless: bool = False,
    subsampling: str = "4:2:0",
    color_profile_mode: str = "srgb",
    exif_mode: str = "preserve",
    bg_color: Union[str, Tuple[int, int, int]] = "#FFFFFF",
    extract_all_frames: bool = False,
) -> List[Path]:
    """
    Converte um arquivo de imagem para qualquer um dos 18 formatos suportados.
    Inclui suporte completo a HEIF/HEIC do iPhone (entrada e saída), conversão de perfil ICC
    Display P3 -> sRGB, preservação seletiva de EXIF/GPS e extração opcional de múltiplos quadros.
    """
    ensure_heif_registered()

    source_path = Path(source_path)
    output_path = Path(output_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"Imagem de origem não encontrada: {source_path}")

    fmt_key = target_format.strip().upper().lstrip(".")
    if fmt_key not in PILLOW_FORMAT_MAP:
        raise ValueError(f"Formato de saída não suportado: '{target_format}'")

    pillow_format = PILLOW_FORMAT_MAP[fmt_key]
    bg_rgb = parse_bg_color(bg_color)
    target_supports_icc = pillow_format in ICC_CAPABLE_PILLOW_FORMATS

    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_files: List[Path] = []

    with Image.open(source_path) as opened:
        raw_icc = opened.info.get("icc_profile")
        exif_bytes = _build_exif_bytes(opened, exif_mode)
        total_frames = getattr(opened, "n_frames", 1) or 1
        frames_to_process = total_frames if (extract_all_frames and total_frames > 1) else 1

        clean_stem = _clean_frame_stem(output_path)
        real_ext = OUTPUT_EXTENSION_MAP[fmt_key]

        for frame_idx in range(frames_to_process):
            if frame_idx > 0:
                try:
                    opened.seek(frame_idx)
                except EOFError:
                    break

            transposed = ImageOps.exif_transpose(opened)
            color_fixed, out_icc = _apply_color_profile(
                transposed,
                raw_icc,
                color_profile_mode=color_profile_mode,
                target_supports_icc=target_supports_icc,
            )
            prepared = _prepare_image_mode(color_fixed, pillow_format, bg_rgb)
            if prepared is opened:
                prepared = prepared.copy()

            if out_icc is None or not target_supports_icc:
                prepared.info.pop("icc_profile", None)
            if exif_bytes is None or pillow_format not in EXIF_CAPABLE_PILLOW_FORMATS:
                prepared.info.pop("exif", None)
                try:
                    prepared.getexif().clear()
                except Exception:
                    pass

            save_kwargs = _build_save_kwargs(
                pillow_format=pillow_format,
                quality=quality,
                lossless=lossless,
                subsampling=subsampling,
                exif_bytes=exif_bytes,
                icc_bytes=out_icc,
            )

            dest = (
                output_path
                if frame_idx == 0
                else (output_path.parent / f"{clean_stem}_quadro{frame_idx + 1:02d}{real_ext}")
            )
            prepared.save(dest, format=pillow_format, **save_kwargs)
            generated_files.append(dest)

    return generated_files
