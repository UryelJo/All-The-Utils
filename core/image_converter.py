import os
from PIL import Image

SUPPORTED_INPUTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif", ".ico"}
SUPPORTED_OUTPUTS = ["PNG", "JPG", "WEBP", "ICO", "BMP", "TIFF", "PDF"]

def convert_single_image(input_path: str, output_format: str, output_dir: str = None, quality: int = 90) -> str:
    """
    Converte uma única imagem para o formato especificado.
    Retorna o caminho do arquivo convertido.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    output_format = output_format.upper()
    if output_format == "JPG":
        output_format = "JPEG"

    dir_name = output_dir if output_dir else os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    ext = output_format.lower()
    if ext == "jpeg":
        ext = "jpg"

    output_path = os.path.join(dir_name, f"{base_name}.{ext}")

    # Evita sobrescrever o mesmo arquivo caso a extensão de entrada e saída sejam iguais na mesma pasta
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        output_path = os.path.join(dir_name, f"{base_name}_converted.{ext}")

    with Image.open(input_path) as img:
        # Se for salvar em JPEG ou PDF e a imagem tiver canal Alpha (RGBA), converter para RGB
        if output_format in ["JPEG", "PDF"] and img.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            rgb_img.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            target_img = rgb_img
        elif output_format == "ICO":
            # Redimensiona para formato padrão de ícone compatível se for muito grande
            target_img = img.copy()
            if target_img.size[0] > 256 or target_img.size[1] > 256:
                target_img.thumbnail((256, 256), Image.Resampling.LANCZOS)
        else:
            target_img = img

        save_kwargs = {}
        if output_format in ["JPEG", "WEBP"]:
            save_kwargs["quality"] = quality

        target_img.save(output_path, format=output_format, **save_kwargs)

    return output_path
