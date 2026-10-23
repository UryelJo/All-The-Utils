"""
Lógica pura de redimensionamento, corte e transformação de imagens.
Isolada de interface gráfica para garantir testabilidade unitária e execução em workers.
"""
from pathlib import Path
from typing import Any, Dict, Tuple
from PIL import Image, ImageOps

RESIZE_MODES = [
    "Porcentagem",
    "Largura Máxima (Manter Proporção)",
    "Altura Máxima (Manter Proporção)",
    "Caixa Exata (Largura x Altura)"
]

FIT_MODES = [
    "Ajustar com Barras (Fit)",
    "Preencher e Cortar (Fill / Crop)",
    "Distorcer (Stretch)"
]

RESAMPLE_FILTERS = {
    "Lanczos (Alta Qualidade)": Image.Resampling.LANCZOS,
    "Bicúbica": Image.Resampling.BICUBIC,
    "Bilinear": Image.Resampling.BILINEAR,
    "Vizinho Mais Próximo": Image.Resampling.NEAREST
}

ROTATION_OPTIONS = [
    "Nenhuma",
    "90° Horário",
    "180°",
    "270° Horário",
    "Orientação Automática EXIF"
]

def calculate_new_dimensions(
    orig_w: int,
    orig_h: int,
    mode: str,
    percent: int = 50,
    target_w: int = 1920,
    target_h: int = 1080,
    keep_aspect: bool = True
) -> Tuple[int, int]:
    """Calcula as dimensões finais de acordo com as regras especificadas."""
    if orig_w <= 0 or orig_h <= 0:
        return (1, 1)

    if mode == "Porcentagem":
        ratio = max(percent, 1) / 100.0
        return (max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio)))

    if mode == "Largura Máxima (Manter Proporção)":
        if orig_w <= target_w:
            return (orig_w, orig_h)
        ratio = target_w / float(orig_w)
        return (target_w, max(1, int(orig_h * ratio)))

    if mode == "Altura Máxima (Manter Proporção)":
        if orig_h <= target_h:
            return (orig_w, orig_h)
        ratio = target_h / float(orig_h)
        return (max(1, int(orig_w * ratio)), target_h)

    # Caixa Exata (Largura x Altura)
    if not keep_aspect:
        return (target_w, target_h)

    # Mantendo proporção dentro da caixa
    ratio = min(target_w / float(orig_w), target_h / float(orig_h))
    return (max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio)))

def resize_single_image(src: Path, dst: Path, params: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """
    Redimensiona uma imagem aplicando opções de modo, interpolação, rotação e corte.
    Retorna (orig_w, orig_h, new_w, new_h).
    """
    mode = params.get("mode", "Porcentagem")
    percent = params.get("percent", 50)
    target_w = params.get("width", 1920)
    target_h = params.get("height", 1080)
    keep_aspect = params.get("keep_aspect", True)
    fit_mode = params.get("fit_mode", "Ajustar com Barras (Fit)")
    filter_name = params.get("filter", "Lanczos (Alta Qualidade)")
    rotation = params.get("rotation", "Nenhuma")
    flip_h = params.get("flip_h", False)
    flip_v = params.get("flip_v", False)

    resample_filter = RESAMPLE_FILTERS.get(filter_name, Image.Resampling.LANCZOS)

    with Image.open(src) as im:
        # 1. Rotação / Orientação
        if rotation == "Orientação Automática EXIF":
            im = ImageOps.exif_transpose(im) or im
        elif rotation == "90° Horário":
            im = im.rotate(-90, expand=True)
        elif rotation == "180°":
            im = im.rotate(180, expand=True)
        elif rotation == "270° Horário":
            im = im.rotate(-270, expand=True)

        # 2. Espelhamento
        if flip_h:
            im = ImageOps.mirror(im)
        if flip_v:
            im = ImageOps.flip(im)

        orig_w, orig_h = im.size

        # 3. Cálculo das dimensões e redimensionamento
        if mode == "Caixa Exata (Largura x Altura)" and fit_mode == "Preencher e Cortar (Fill / Crop)":
            # ImageOps.fit corta o excedente para preencher toda a caixa
            im_resized = ImageOps.fit(im, (target_w, target_h), method=resample_filter)
            final_w, final_h = target_w, target_h
        elif mode == "Caixa Exata (Largura x Altura)" and fit_mode == "Ajustar com Barras (Fit)":
            # Redimensiona proporcional e cria fundo com barras (transparente ou preto)
            scaled_w, scaled_h = calculate_new_dimensions(orig_w, orig_h, mode, percent, target_w, target_h, True)
            im_scaled = im.resize((scaled_w, scaled_h), resample=resample_filter)

            # Imagem base
            has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            if has_alpha:
                base = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            else:
                base = Image.new("RGB", (target_w, target_h), (255, 255, 255))

            pos_x = (target_w - scaled_w) // 2
            pos_y = (target_h - scaled_h) // 2

            if has_alpha:
                base.paste(im_scaled, (pos_x, pos_y), im_scaled.convert("RGBA"))
            else:
                base.paste(im_scaled, (pos_x, pos_y))
            im_resized = base
            final_w, final_h = target_w, target_h
        else:
            new_w, new_h = calculate_new_dimensions(orig_w, orig_h, mode, percent, target_w, target_h, keep_aspect)
            im_resized = im.resize((new_w, new_h), resample=resample_filter)
            final_w, final_h = new_w, new_h

        # 4. Salvar resultado garantindo compatibilidade de formato
        dst.parent.mkdir(parents=True, exist_ok=True)
        ext = dst.suffix.lower()

        if ext in (".jpg", ".jpeg"):
            if im_resized.mode in ("RGBA", "LA", "P"):
                rgb_im = Image.new("RGB", im_resized.size, (255, 255, 255))
                if im_resized.mode == "RGBA":
                    rgb_im.paste(im_resized, mask=im_resized.split()[3])
                else:
                    rgb_im.paste(im_resized.convert("RGB"))
                rgb_im.save(dst, format="JPEG", quality=92, optimize=True)
            else:
                im_resized.save(dst, format="JPEG", quality=92, optimize=True)
        elif ext == ".png":
            im_resized.save(dst, format="PNG", optimize=True)
        elif ext == ".webp":
            im_resized.save(dst, format="WEBP", quality=90)
        else:
            im_resized.save(dst)

        return (orig_w, orig_h, final_w, final_h)
