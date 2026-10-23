"""
Lógica pura de aplicação de marcas d'água (Texto ou Logo/Imagem) em imagens.
"""
import math
from pathlib import Path
from typing import Any, Dict
from PIL import Image, ImageDraw, ImageFont

WATERMARK_POSITIONS = [
    "Inferior Direito",
    "Inferior Esquerdo",
    "Superior Direito",
    "Superior Esquerdo",
    "Centro",
    "Mosaico Repetido (Tiled)"
]

def _get_font(font_size: int):
    """Tenta carregar fonte padrão do Windows (Segoe UI / Arial) ou fallback para default."""
    font_paths = [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
    ]
    for fp in font_paths:
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), font_size)
            except Exception:
                pass
    return ImageFont.load_default()

def apply_watermark_to_image(src: Path, dst: Path, params: Dict[str, Any]) -> None:
    """Aplica marca d'água de texto ou imagem/logo com controle fino de transparência e posição."""
    wm_type = params.get("type", "Texto")
    pos = params.get("position", "Inferior Direito")
    opacity = max(0.05, min(1.0, params.get("opacity", 50) / 100.0))
    margin = params.get("margin", 25)

    with Image.open(src) as base_im:
        # Trabalha com cópia em RGBA para suporte perfeito à transparência
        orig_mode = base_im.mode
        is_transparent = orig_mode in ("RGBA", "LA") or (orig_mode == "P" and "transparency" in base_im.info)
        base_rgba = base_im.convert("RGBA")
        bw, bh = base_rgba.size

        watermark_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))

        if wm_type == "Texto":
            text = params.get("text", "All the Utils")
            font_size = params.get("font_size", 36)
            font = _get_font(font_size)
            rotation = params.get("rotation", 0)
            color_hex = params.get("color", "#FFFFFF").lstrip("#")

            # Converte hex para RGB
            try:
                r = int(color_hex[0:2], 16)
                g = int(color_hex[2:4], 16)
                b = int(color_hex[4:6], 16)
            except Exception:
                r, g, b = 255, 255, 255
            alpha = int(255 * opacity)

            # Calcula dimensões do texto
            dummy_draw = ImageDraw.Draw(watermark_layer)
            bbox = dummy_draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # Cria imagem pequena para o texto (permitindo rotação independente)
            txt_im = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_im)
            txt_draw.text((10, 10), text, font=font, fill=(r, g, b, alpha))

            if rotation != 0:
                txt_im = txt_im.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
                tw, th = txt_im.size

            if pos == "Mosaico Repetido (Tiled)":
                step_x = max(tw + 80, 100)
                step_y = max(th + 80, 100)
                for y in range(0, bh, step_y):
                    for x in range(0, bw, step_x):
                        watermark_layer.paste(txt_im, (x, y), txt_im)
            else:
                if pos == "Inferior Direito":
                    x = bw - tw - margin
                    y = bh - th - margin
                elif pos == "Inferior Esquerdo":
                    x = margin
                    y = bh - th - margin
                elif pos == "Superior Direito":
                    x = bw - tw - margin
                    y = margin
                elif pos == "Superior Esquerdo":
                    x = margin
                    y = margin
                else:  # Centro
                    x = (bw - tw) // 2
                    y = (bh - th) // 2

                watermark_layer.paste(txt_im, (x, y), txt_im)

        else:
            # Imagem / Logo
            logo_path = Path(params.get("logo_path", ""))
            if logo_path.exists() and logo_path.is_file():
                with Image.open(logo_path) as logo_im:
                    logo_rgba = logo_im.convert("RGBA")
                    lw, lh = logo_rgba.size

                    # Escala em relação à largura base
                    scale_pct = params.get("logo_scale", 20) / 100.0
                    target_lw = max(16, int(bw * scale_pct))
                    target_lh = max(16, int(lh * (target_lw / float(lw))))
                    logo_resized = logo_rgba.resize((target_lw, target_lh), resample=Image.Resampling.LANCZOS)

                    # Aplica opacidade na camada alfa do logo
                    r_ch, g_ch, b_ch, a_ch = logo_resized.split()
                    a_ch = a_ch.point(lambda p: int(p * opacity))
                    logo_resized.putalpha(a_ch)

                    lw, lh = target_lw, target_lh

                    if pos == "Mosaico Repetido (Tiled)":
                        step_x = max(lw + 80, 100)
                        step_y = max(lh + 80, 100)
                        for y in range(0, bh, step_y):
                            for x in range(0, bw, step_x):
                                watermark_layer.paste(logo_resized, (x, y), logo_resized)
                    else:
                        if pos == "Inferior Direito":
                            x = bw - lw - margin
                            y = bh - lh - margin
                        elif pos == "Inferior Esquerdo":
                            x = margin
                            y = bh - lh - margin
                        elif pos == "Superior Direito":
                            x = bw - lw - margin
                            y = margin
                        elif pos == "Superior Esquerdo":
                            x = margin
                            y = margin
                        else:  # Centro
                            x = (bw - lw) // 2
                            y = (bh - lh) // 2

                        watermark_layer.paste(logo_resized, (x, y), logo_resized)

        # Mescla camada de marca d'água sobre a imagem base
        final_im = Image.alpha_composite(base_rgba, watermark_layer)

        dst.parent.mkdir(parents=True, exist_ok=True)
        ext = dst.suffix.lower()

        if ext in (".jpg", ".jpeg"):
            rgb_out = final_im.convert("RGB")
            rgb_out.save(dst, format="JPEG", quality=92, optimize=True)
        elif ext == ".png":
            if is_transparent:
                final_im.save(dst, format="PNG", optimize=True)
            else:
                final_im.convert("RGB").save(dst, format="PNG", optimize=True)
        elif ext == ".webp":
            final_im.save(dst, format="WEBP", quality=90)
        else:
            final_im.save(dst)
