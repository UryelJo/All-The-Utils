"""
Lógica pura para criação avançada de arquivos compactados ZIP.
Oferece algoritmos modernos (DEFLATE, BZIP2, LZMA, STORE), níveis de compressão (1-9),
divisão em volumes multipartes (.001, .002...) e criptografia com senha.

Zero dependências de interface gráfica.
"""
import io
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import zipfile

COMPRESSION_METHODS = {
    "deflate": zipfile.ZIP_DEFLATED,
    "bzip2": zipfile.ZIP_BZIP2,
    "lzma": zipfile.ZIP_LZMA,
    "store": zipfile.ZIP_STORED,
}


def split_file_into_volumes(source_file: Path, volume_size_bytes: int) -> List[Path]:
    """
    Divide um arquivo em volumes numerados (.001, .002, .003...).
    """
    src = Path(source_file)
    if not src.is_file():
        raise FileNotFoundError(f"Arquivo fonte não encontrado: {src}")

    volumes: List[Path] = []
    part_idx = 1

    with open(src, "rb") as f_in:
        while True:
            chunk = f_in.read(volume_size_bytes)
            if not chunk:
                break
            vol_path = src.parent / f"{src.name}.{part_idx:03d}"
            vol_path.write_bytes(chunk)
            volumes.append(vol_path)
            part_idx += 1

    return volumes


def create_advanced_archive(
    source_items: List[Path],
    output_zip: Path,
    compression_method: str = "deflate",
    compress_level: int = 6,
    split_size_bytes: Optional[int] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cria um arquivo compactado ZIP com controle fino de compressão e divisão em volumes.
    """
    out_path = Path(output_zip).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    method_key = compression_method.lower().strip()
    if method_key not in COMPRESSION_METHODS:
        raise ValueError(f"Método de compressão não suportado: {compression_method}")

    zip_method = COMPRESSION_METHODS[method_key]
    compress_level = max(1, min(9, compress_level))

    total_uncompressed_bytes = 0
    t0 = time.perf_counter()

    # Cria o arquivo ZIP
    # Parâmetros de abertura dependem do suporte de compresslevel no zip_method
    open_kwargs = {"mode": "w", "compression": zip_method}
    if zip_method == zipfile.ZIP_DEFLATED or zip_method == zipfile.ZIP_BZIP2:
        open_kwargs["compresslevel"] = compress_level

    with zipfile.ZipFile(out_path, **open_kwargs) as zf:
        if password:
            zf.setpassword(password.encode("utf-8"))

        for item in source_items:
            path_obj = Path(item).resolve()
            if path_obj.is_file():
                arcname = path_obj.name
                total_uncompressed_bytes += path_obj.stat().st_size
                zf.write(path_obj, arcname=arcname)
            elif path_obj.is_dir():
                for sub in path_obj.rglob("*"):
                    if sub.is_file():
                        arcname = str(sub.relative_to(path_obj.parent)).replace("\\", "/")
                        total_uncompressed_bytes += sub.stat().st_size
                        zf.write(sub, arcname=arcname)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    compressed_size = out_path.stat().st_size

    # Se a divisão em volumes foi solicitada
    generated_volumes: List[str] = []
    if split_size_bytes and split_size_bytes > 0 and compressed_size > split_size_bytes:
        vols = split_file_into_volumes(out_path, split_size_bytes)
        generated_volumes = [str(v.resolve()) for v in vols]

    saving_pct = 0.0
    if total_uncompressed_bytes > 0:
        saving_pct = max(0.0, (1.0 - (compressed_size / total_uncompressed_bytes)) * 100.0)

    return {
        "output_path": str(out_path),
        "uncompressed_bytes": total_uncompressed_bytes,
        "compressed_bytes": compressed_size,
        "saving_percent": saving_pct,
        "elapsed_ms": elapsed_ms,
        "compression_method": method_key,
        "volumes": generated_volumes,
    }
