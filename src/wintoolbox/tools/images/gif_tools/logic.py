"""
Lógica pura para criação de GIFs animados e extração de frames via Pillow.
Isolada de qualquer dependência de interface gráfica.
"""
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image, ImageSequence


def create_animated_gif(
    image_paths: List[Path],
    output_path: Path,
    frame_duration_ms: int = 200,
    loop: int = 0,
    max_size: Optional[Tuple[int, int]] = (800, 800),
    optimize: bool = True
) -> Path:
    """
    Combina uma lista ordenada de imagens em um arquivo GIF animado.
    """
    if not image_paths:
        raise ValueError("A lista de imagens está vazia.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames: List[Image.Image] = []

    # Determina o tamanho alvo baseado na primeira imagem válida
    first_path = Path(image_paths[0])
    with Image.open(first_path) as first_img:
        base_w, base_h = first_img.size
        if max_size:
            max_w, max_h = max_size
            ratio = min(max_w / base_w, max_h / base_h, 1.0)
            target_w = max(1, int(base_w * ratio))
            target_h = max(1, int(base_h * ratio))
        else:
            target_w, target_h = base_w, base_h

    for p in image_paths:
        path_obj = Path(p)
        if not path_obj.is_file():
            continue

        with Image.open(path_obj) as img_raw:
            # Converte RGBA para RGB com fundo branco se necessário
            if img_raw.mode in ("RGBA", "LA") or (img_raw.mode == "P" and "transparency" in img_raw.info):
                bg = Image.new("RGB", img_raw.size, (255, 255, 255))
                alpha = img_raw.convert("RGBA").split()[3]
                bg.paste(img_raw.convert("RGB"), mask=alpha)
                frame = bg
            else:
                frame = img_raw.convert("RGB")

            # Redimensiona para manter proporção dentro do canvas padrão
            frame_resized = frame.resize((target_w, target_h), Image.Resampling.LANCZOS)
            # Quantiza paleta para 256 cores (P mode necessário para GIF)
            frame_quant = frame_resized.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
            frames.append(frame_quant)

    if not frames:
        raise ValueError("Nenhuma imagem válida pôde ser processada para o GIF.")

    first_frame = frames[0]
    other_frames = frames[1:] if len(frames) > 1 else []

    first_frame.save(
        output_path,
        format="GIF",
        save_all=True,
        append_images=other_frames,
        duration=max(20, frame_duration_ms),
        loop=loop,
        optimize=optimize
    )

    return output_path


def extract_gif_frames(
    gif_path: Path,
    output_dir: Path,
    output_format: str = "PNG"
) -> List[Path]:
    """
    Extrai todos os quadros (frames) individuais de um arquivo GIF animado.
    """
    gif_path = Path(gif_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not gif_path.is_file():
        raise FileNotFoundError(f"Arquivo GIF não encontrado: {gif_path}")

    ext = output_format.lower()
    if ext == "jpeg":
        ext = "jpg"

    saved_frames: List[Path] = []

    with Image.open(gif_path) as img:
        for idx, frame in enumerate(ImageSequence.Iterator(img)):
            frame_rgb = frame.convert("RGBA" if ext == "png" else "RGB")
            out_file = output_dir / f"frame_{idx + 1:04d}.{ext}"
            frame_rgb.save(out_file)
            saved_frames.append(out_file)

    if not saved_frames:
        raise ValueError("Nenhum quadro pôde ser extraído do arquivo GIF.")

    return saved_frames
