"""
Lógica pura para remoção de fundo de imagens (Chroma Key, fundo sólido e detecção inteligente de bordas)
com suporte a substituição de fundo por cor sólida ou outra imagem.
Isolada de qualquer interface gráfica.
"""
import io
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageOps


def remove_image_background(
    input_path: Path,
    output_path: Path,
    mode: str = "auto_corners",
    custom_color: Optional[Tuple[int, int, int]] = None,
    tolerance: int = 35,
    feather: int = 8,
    bg_replacement_mode: str = "transparent",
    bg_solid_color: Tuple[int, int, int] = (255, 255, 255),
    bg_custom_image_path: Optional[Path] = None
) -> Path:
    """
    Remove o fundo de uma imagem e salva o resultado com canal alpha ou com fundo substituído.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    # Processamento nativo via Pillow
    with Image.open(input_path) as img_raw:
        img_rgb = ImageOps.exif_transpose(img_raw).convert("RGB")
        width, height = img_rgb.size

        # Determina a cor de referência de fundo
        if mode == "custom" and custom_color:
            target_r, target_g, target_b = custom_color
        elif mode == "white":
            target_r, target_g, target_b = 255, 255, 255
        elif mode == "black":
            target_r, target_g, target_b = 0, 0, 0
        else:
            # Amostra a média dos 4 cantos
            c1 = img_rgb.getpixel((0, 0))
            c2 = img_rgb.getpixel((width - 1, 0))
            c3 = img_rgb.getpixel((0, height - 1))
            c4 = img_rgb.getpixel((width - 1, height - 1))
            target_r = int((c1[0] + c2[0] + c3[0] + c4[0]) / 4)
            target_g = int((c1[1] + c2[1] + c3[1] + c4[1]) / 4)
            target_b = int((c1[2] + c2[2] + c3[2] + c4[2]) / 4)

        img_rgba = img_rgb.convert("RGBA")
        raw_bytes = bytearray(img_rgba.tobytes())

        tol_sq = tolerance * tolerance
        feather_sq = (tolerance + feather) * (tolerance + feather)
        diff_sq = feather_sq - tol_sq if feather_sq > tol_sq else 1.0

        for i in range(0, len(raw_bytes), 4):
            r = raw_bytes[i]
            g = raw_bytes[i + 1]
            b = raw_bytes[i + 2]

            dist_sq = ((r - target_r) ** 2) + ((g - target_g) ** 2) + ((b - target_b) ** 2)

            if dist_sq <= tol_sq:
                raw_bytes[i + 3] = 0
            elif dist_sq >= feather_sq:
                raw_bytes[i + 3] = 255
            else:
                ratio = (dist_sq - tol_sq) / diff_sq
                raw_bytes[i + 3] = max(0, min(255, int(255 * ratio)))

        result_img = Image.frombytes("RGBA", (width, height), bytes(raw_bytes))

        # Substituição de Fundo
        if bg_replacement_mode == "solid":
            bg = Image.new("RGBA", (width, height), bg_solid_color + (255,))
            bg.paste(result_img, (0, 0), result_img)
            result_img = bg
        elif bg_replacement_mode == "custom_image" and bg_custom_image_path and Path(bg_custom_image_path).is_file():
            with Image.open(bg_custom_image_path) as bg_raw:
                bg_fitted = ImageOps.fit(bg_raw.convert("RGBA"), (width, height), method=Image.Resampling.LANCZOS)
                bg_fitted.paste(result_img, (0, 0), result_img)
                result_img = bg_fitted

        ext = output_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            result_img.convert("RGB").save(output_path, "JPEG", quality=95)
        elif ext == ".webp":
            result_img.save(output_path, "WEBP", quality=95)
        else:
            result_img.save(output_path, "PNG", optimize=True)

    return output_path


def render_remove_bg_preview(input_path: Path, params: Dict[str, Any]) -> Image.Image:
    """Gera visualização rápida em memória."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        remove_image_background(
            input_path=input_path,
            output_path=tmp_path,
            mode=params.get("mode", "auto_corners"),
            custom_color=params.get("custom_color"),
            tolerance=int(params.get("tolerance", 35)),
            feather=int(params.get("feather", 8)),
            bg_replacement_mode=params.get("bg_replacement_mode", "transparent"),
            bg_solid_color=params.get("bg_solid_color", (255, 255, 255)),
            bg_custom_image_path=params.get("bg_custom_image_path"),
        )
        with Image.open(tmp_path) as im:
            return im.copy()
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
