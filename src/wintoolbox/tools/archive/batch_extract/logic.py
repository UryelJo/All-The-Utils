"""
Lógica pura de extração em lote de múltiplos arquivos compactados.
Suporta ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, com opções de criação de subpastas,
detecção inteligente de raiz duplicada e remoção segura da origem pós-sucesso.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import Any, Callable, Dict, List, Optional
import zipfile


def is_safe_relative_path(base_dir: Path, target_path_str: str) -> bool:
    """
    Verifica se o caminho do membro não escapa do diretório base (proteção Zip Slip).
    """
    base = base_dir.resolve()
    target = (base / target_path_str).resolve()
    try:
        return target.is_relative_to(base)
    except AttributeError:
        return str(target).startswith(str(base))


def detect_single_root_folder_zip(zf: zipfile.ZipFile) -> Optional[str]:
    """
    Verifica se todos os arquivos e pastas dentro do ZIP residem dentro de um único diretório raiz.
    Se sim, retorna o nome dessa pasta raiz para evitar aninhamento duplo.
    """
    names = [name for name in zf.namelist() if name.strip()]
    if not names:
        return None

    first_parts = set()
    for name in names:
        norm = name.replace("\\", "/").strip("/")
        parts = norm.split("/")
        if parts:
            first_parts.add(parts[0])

    if len(first_parts) == 1:
        candidate = list(first_parts)[0]
        # Confirma que é uma pasta ou prefixo comum
        return candidate
    return None


def detect_single_root_folder_tar(tf: tarfile.TarFile) -> Optional[str]:
    """
    Verifica se todos os membros do TAR residem dentro de uma pasta raiz comum.
    """
    members = tf.getmembers()
    if not members:
        return None

    first_parts = set()
    for m in members:
        norm = m.name.replace("\\", "/").strip("/")
        parts = norm.split("/")
        if parts:
            first_parts.add(parts[0])

    if len(first_parts) == 1:
        return list(first_parts)[0]
    return None


def find_system_extractor() -> Optional[str]:
    """Localiza 7-Zip ou UnRAR instalado no sistema operacional."""
    for name in ["7z.exe", "7z", "unrar.exe", "unrar"]:
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files\WinRAR\WinRAR.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def extract_archive_item(
    archive_path: Path,
    output_dir: Path,
    create_subfolder: bool = True,
    avoid_duplicate_root: bool = True,
    delete_source_after: bool = False,
    password: Optional[str] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """
    Processa a extração de um único arquivo compactado.
    """
    archive_path = Path(archive_path).resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Arquivo compactado não encontrado: {archive_path}")

    lower_name = archive_path.name.lower()

    # Define o nome da pasta de destino base
    stem = archive_path.stem
    if lower_name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        stem = Path(stem).stem

    dest_folder = output_dir.resolve()
    if create_subfolder:
        dest_folder = dest_folder / stem

    dest_folder.mkdir(parents=True, exist_ok=True)
    extracted_count = 0
    total_bytes = 0

    pwd_bytes = password.encode("utf-8") if password else None

    if lower_name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            if pwd_bytes:
                zf.setpassword(pwd_bytes)

            root_prefix = None
            if avoid_duplicate_root and create_subfolder:
                single_root = detect_single_root_folder_zip(zf)
                if single_root and single_root.lower() == stem.lower():
                    # Evita duplicar a pasta stem/stem/
                    root_prefix = single_root

            members = zf.infolist()
            total_items = len(members)

            for idx, info in enumerate(members):
                rel_path = info.filename
                if root_prefix:
                    # Remove o prefixo da raiz comum
                    norm = rel_path.replace("\\", "/").strip("/")
                    if norm == root_prefix:
                        continue
                    if norm.startswith(root_prefix + "/"):
                        rel_path = norm[len(root_prefix) + 1 :]

                if not is_safe_relative_path(dest_folder, rel_path):
                    raise ValueError(
                        f"Ataque Path Traversal detectado no arquivo: {info.filename}"
                    )

                out_target = dest_folder / rel_path
                if info.is_dir():
                    out_target.mkdir(parents=True, exist_ok=True)
                else:
                    out_target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as src_f, open(out_target, "wb") as dst_f:
                        shutil.copyfileobj(src_f, dst_f)
                    extracted_count += 1
                    total_bytes += info.file_size

                if progress_cb and total_items > 0:
                    progress_cb(int(((idx + 1) / total_items) * 100))

    elif lower_name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(archive_path, "r:*") as tf:
            root_prefix = None
            if avoid_duplicate_root and create_subfolder:
                single_root = detect_single_root_folder_tar(tf)
                if single_root and single_root.lower() == stem.lower():
                    root_prefix = single_root

            members = tf.getmembers()
            total_items = len(members)

            for idx, member in enumerate(members):
                rel_path = member.name
                if root_prefix:
                    norm = rel_path.replace("\\", "/").strip("/")
                    if norm == root_prefix:
                        continue
                    if norm.startswith(root_prefix + "/"):
                        rel_path = norm[len(root_prefix) + 1 :]

                if not is_safe_relative_path(dest_folder, rel_path):
                    raise ValueError(
                        f"Ataque Path Traversal detectado no arquivo: {member.name}"
                    )

                out_target = dest_folder / rel_path
                if member.isdir():
                    out_target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    out_target.parent.mkdir(parents=True, exist_ok=True)
                    extracted_file = tf.extractfile(member)
                    if extracted_file:
                        with open(out_target, "wb") as dst_f:
                            shutil.copyfileobj(extracted_file, dst_f)
                        extracted_count += 1
                        total_bytes += member.size

                if progress_cb and total_items > 0:
                    progress_cb(int(((idx + 1) / total_items) * 100))

    elif lower_name.endswith((".7z", ".rar")):
        extractor = find_system_extractor()
        if extractor:
            cmd = [extractor, "x", "-y", f"-o{str(dest_folder)}", str(archive_path)]
            if password:
                cmd.append(f"-p{password}")
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"Erro na extração de {archive_path.name}: {res.stderr}")
            # Conta arquivos gerados
            for r, _, fl in os.walk(dest_folder):
                for f in fl:
                    extracted_count += 1
                    total_bytes += (Path(r) / f).stat().st_size
        else:
            # Tenta via utilitário bsdtar nativo do Windows (C:\Windows\System32\tar.exe)
            bsdtar = shutil.which("tar") or r"C:\Windows\System32\tar.exe"
            if os.path.isfile(bsdtar):
                cmd = [bsdtar, "-xf", str(archive_path), "-C", str(dest_folder)]
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode != 0:
                    raise RuntimeError(
                        f"Não foi possível descompactar {archive_path.name}. Instale 7-Zip ou WinRAR."
                    )
                for r, _, fl in os.walk(dest_folder):
                    for f in fl:
                        extracted_count += 1
                        total_bytes += (Path(r) / f).stat().st_size
            else:
                raise RuntimeError(
                    f"Formato {archive_path.suffix} requer 7-Zip ou WinRAR instalado."
                )
    else:
        raise ValueError(f"Formato não suportado para extração: {archive_path.suffix}")

    # Deleção pós-sucesso se solicitado
    if delete_source_after:
        archive_path.unlink(missing_ok=True)

    return {
        "status": "OK",
        "archive_name": archive_path.name,
        "dest_folder": str(dest_folder),
        "files_count": extracted_count,
        "total_bytes": total_bytes,
        "source_deleted": delete_source_after,
    }
