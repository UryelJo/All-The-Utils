"""
Lógica pura do Assistente de Backup Incremental e Snapshot de Pastas Locais.
Identifica arquivos novos e modificados desde o último backup via manifesto JSON e executa backup para pasta ou ZIP.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Callable, Dict, List, Optional, Tuple
import zipfile

MANIFEST_NAME = ".wtx_backup_manifest.json"


@dataclass
class BackupReport:
    timestamp: str
    source_dir: Path
    target_path: Path
    files_copied: int
    bytes_copied: int
    files_skipped: int
    backup_mode: str  # "folder" ou "zip"


def load_manifest(manifest_path: Path) -> Dict[str, Tuple[float, int]]:
    """Carrega o histórico de arquivos do último backup."""
    if not manifest_path.is_file():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # data: {rel_path: [mtime, size]}
            return {k: (v[0], v[1]) for k, v in data.items()}
    except Exception:
        return {}


def save_manifest(manifest_path: Path, state: Dict[str, Tuple[float, int]]) -> None:
    """Salva o estado atual de arquivos do backup no manifesto JSON."""
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def run_incremental_backup(
    source_dir: Path,
    target_base: Path,
    backup_mode: str = "folder",  # "folder" ou "zip"
    compress_level: int = 6,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> BackupReport:
    """
    Executa o backup diferencial/incremental de source_dir para target_base.
    """
    source_dir = Path(source_dir).resolve()
    target_base = Path(target_base).resolve()

    if not source_dir.is_dir():
        raise FileNotFoundError(f"Pasta de origem não encontrada: {source_dir}")

    target_base.mkdir(parents=True, exist_ok=True)
    manifest_path = target_base / MANIFEST_NAME
    last_state = load_manifest(manifest_path) if backup_mode == "folder" else {}
    current_state: Dict[str, Tuple[float, int]] = {}

    all_files: List[Tuple[Path, str, float, int]] = []
    for root, _, files in os.walk(source_dir):
        for f in files:
            full = Path(root) / f
            try:
                st = full.stat()
                rel = str(full.relative_to(source_dir)).replace("\\", "/")
                all_files.append((full, rel, st.st_mtime, st.st_size))
                current_state[rel] = (st.st_mtime, st.st_size)
            except Exception:
                continue

    total_files = len(all_files)
    files_copied = 0
    bytes_copied = 0
    files_skipped = 0

    now_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # MODO 1: Backup para Arquivo ZIP com Timestamp
    if backup_mode == "zip":
        zip_name = f"backup_{source_dir.name}_{now_str}.zip"
        zip_target = target_base / zip_name

        with zipfile.ZipFile(zip_target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compress_level) as zf:
            for idx, (full, rel, mtime, sz) in enumerate(all_files, start=1):
                zf.write(full, arcname=rel)
                files_copied += 1
                bytes_copied += sz
                if progress_cb and idx % 10 == 0:
                    progress_cb(idx, total_files, f"Compactando: {full.name}")

        return BackupReport(
            timestamp=now_str,
            source_dir=source_dir,
            target_path=zip_target,
            files_copied=files_copied,
            bytes_copied=bytes_copied,
            files_skipped=files_skipped,
            backup_mode="zip",
        )

    # MODO 2: Backup Incremental para Pasta Espelhada
    dest_dir = target_base / source_dir.name
    dest_dir.mkdir(parents=True, exist_ok=True)

    for idx, (full, rel, mtime, sz) in enumerate(all_files, start=1):
        target_file = dest_dir / rel

        # Compara com manifesto anterior
        last_info = last_state.get(rel)
        if last_info and last_info[0] == mtime and last_info[1] == sz and target_file.is_file():
            files_skipped += 1
            if progress_cb and idx % 20 == 0:
                progress_cb(idx, total_files, f"Sem alterações: {full.name}")
            continue

        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(full), str(target_file))
        files_copied += 1
        bytes_copied += sz

        if progress_cb and idx % 10 == 0:
            progress_cb(idx, total_files, f"Copiando: {full.name}")

    save_manifest(manifest_path, current_state)

    return BackupReport(
        timestamp=now_str,
        source_dir=source_dir,
        target_path=dest_dir,
        files_copied=files_copied,
        bytes_copied=bytes_copied,
        files_skipped=files_skipped,
        backup_mode="folder",
    )
