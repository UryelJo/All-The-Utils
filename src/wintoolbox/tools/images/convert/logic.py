"""
Lógica pura de conversão de imagens usando Pillow.
Independente de interface gráfica para uso em batch, threads e CLI.
"""
from pathlib import Path
from PIL import Image

SUPPORTED_OUTPUTS = ["WEBP", "JPG", "PNG", "ICO", "BMP", "TIFF", "PDF"]

def convert_single_image(
    source_path: Path,
    output_path: Path,
    target_format: str,
    quality: int = 90
) -> None:
    """
    Converte um único arquivo de imagem de forma segura.
    Trata canais de transparência para formatos incompatíveis (como JPEG e PDF).
    """
    target_format = target_format.upper()
    if target_format == "JPG":
        target_format = "JPEG"

    with Image.open(source_path) as img:
        # Tratamento de canal alfa para JPEG e PDF
        if target_format in ("JPEG", "PDF"):
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
                bg.paste(img, mask=mask)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
        elif target_format == "PNG" and img.mode not in ("RGBA", "RGB", "L"):
            img = img.convert("RGBA")

        save_kwargs = {}
        if target_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = max(10, min(100, quality))
            if target_format == "JPEG":
                save_kwargs["optimize"] = True

        if target_format == "ICO":
            sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save(output_path, format="ICO", sizes=sizes)
        else:
            img.save(output_path, format=target_format, **save_kwargs)
