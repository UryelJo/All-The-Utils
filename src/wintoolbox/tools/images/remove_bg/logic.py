"""
Lógica pura para remoção de fundo de imagens (Chroma Key, fundo sólido e detecção inteligente de bordas).
Isolada de qualquer interface gráfica.
"""
import math
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image


def remove_image_background(
    input_path: Path,
    output_path: Path,
    mode: str = "auto_corners",
    custom_color: Optional[Tuple[int, int, int]] = None,
    tolerance: int = 35,
    feather: int = 8
) -> Path:
    """
    Remove o fundo de uma imagem e salva o resultado com canal alpha (transparência PNG).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    # 1. Tenta rembg se instalado no ambiente
    try:
        import rembg
        with open(input_path, "rb") as inp_f:
            inp_bytes = inp_f.read()
            out_bytes = rembg.remove(inp_bytes)
            with open(output_path, "wb") as out_f:
                out_f.write(out_bytes)
            return output_path
    except Exception:
        pass

    # 2. Algoritmo inteligente nativo via Pillow
    with Image.open(input_path) as img_raw:
        img_rgb = img_raw.convert("RGB")
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

        # Processamento de pixels em alta velocidade via buffer de bytes
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
        result_img.save(output_path, "PNG", optimize=True)

    return output_path

