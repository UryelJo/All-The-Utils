"""
Lógica pura do Comparador e Sincronizador de Pastas (Folder Sync & Diff).
Suporta modos de Espelhamento, Atualização Unidirecional e Bidirecional com verificação de tamanho, mtime ou SHA-256.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
from typing import Callable, Dict, List, Optional, Set, Tuple


@dataclass
class SyncDifference:
    rel_path: Path
    src_path: Optional[Path]
    dst_path: Optional[Path]
    action_type: str  # "copy_to_dst", "copy_to_src", "delete_dst", "identical", "skip"
    reason: str
    size_bytes: int = 0
    status: str = "Pendente"
    error: Optional[str] = None


def get_quick_file_hash(path: Path) -> str:
    """Calcula hash rápido dos primeiros 64KB de um arquivo."""
    try:
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            chunk = f.read(65536)
            hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def compare_directories(
    dir_a: Path,
    dir_b: Path,
    mode: str = "mirror",  # "mirror", "update", "bidirectional"
    use_hash: bool = False,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> List[SyncDifference]:
    """
    Compara recursivamente duas pastas e lista todas as ações necessárias para sincronização.
    """
    dir_a = Path(dir_a).resolve()
    dir_b = Path(dir_b).resolve()

    if not dir_a.is_dir() or not dir_b.is_dir():
        return []

    # Mapeia arquivos de A
    files_a: Dict[Path, Path] = {}
    for root, _, files in os.walk(dir_a):
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(dir_a)
            files_a[rel] = full

    # Mapeia arquivos de B
    files_b: Dict[Path, Path] = {}
    for root, _, files in os.walk(dir_b):
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(dir_b)
            files_b[rel] = full

    all_rel_paths: Set[Path] = set(files_a.keys()).union(set(files_b.keys()))
    diffs: List[SyncDifference] = []
    total = len(all_rel_paths)

    for idx, rel in enumerate(sorted(all_rel_paths), start=1):
        if progress_cb and idx % 50 == 0:
            progress_cb(idx, f"Comparando ({idx}/{total}): {rel.name}")

        in_a = rel in files_a
        in_b = rel in files_b
        src = files_a.get(rel)
        dst = files_b.get(rel)

        # 1. Existe apenas em A
        if in_a and not in_b:
            sz = src.stat().st_size if src else 0
            diffs.append(
                SyncDifference(
                    rel_path=rel,
                    src_path=src,
                    dst_path=dir_b / rel,
                    action_type="copy_to_dst",
                    reason="Novo na Origem (A)",
                    size_bytes=sz
                )
            )

        # 2. Existe apenas em B
        elif not in_a and in_b:
            sz = dst.stat().st_size if dst else 0
            if mode == "mirror":
                diffs.append(
                    SyncDifference(
                        rel_path=rel,
                        src_path=None,
                        dst_path=dst,
                        action_type="delete_dst",
                        reason="Órfão no Destino (Será removido)",
                        size_bytes=sz
                    )
                )
            elif mode == "bidirectional":
                diffs.append(
                    SyncDifference(
                        rel_path=rel,
                        src_path=dir_a / rel,
                        dst_path=dst,
                        action_type="copy_to_src",
                        reason="Novo no Destino (Copiar para A)",
                        size_bytes=sz
                    )
                )
            else:
                # No modo update, arquivos órfãos em B são mantidos intactos
                pass

        # 3. Existe em ambos (compara tamanho, data ou hash)
        else:
            try:
                st_a = src.stat()
                st_b = dst.stat()
                sz_a, sz_b = st_a.st_size, st_b.st_size
                mtime_a, mtime_b = st_a.st_mtime, st_b.st_mtime

                diff_reason = None
                action = "identical"

                if sz_a != sz_b:
                    diff_reason = f"Tamanhos diferentes ({sz_a} vs {sz_b} B)"
                elif abs(mtime_a - mtime_b) > 2.0:
                    # Diferença de modificação maior que 2 segundos
                    if mtime_a > mtime_b:
                        diff_reason = "Origem (A) é mais recente"
                        action = "copy_to_dst"
                    else:
                        diff_reason = "Destino (B) é mais recente"
                        action = "copy_to_src" if mode == "bidirectional" else "copy_to_dst"
                elif use_hash:
                    h_a = get_quick_file_hash(src)
                    h_b = get_quick_file_hash(dst)
                    if h_a != h_b:
                        diff_reason = "Conteúdo/hash diferente"
                        action = "copy_to_dst"

                if diff_reason:
                    diffs.append(
                        SyncDifference(
                            rel_path=rel,
                            src_path=src,
                            dst_path=dst,
                            action_type=action,
                            reason=diff_reason,
                            size_bytes=sz_a
                        )
                    )
            except Exception as e:
                diffs.append(
                    SyncDifference(
                        rel_path=rel,
                        src_path=src,
                        dst_path=dst,
                        action_type="skip",
                        reason=f"Erro de acesso: {e}"
                    )
                )

    return diffs


def execute_sync(
    differences: List[SyncDifference],
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[int, int]:
    """
    Aplica as operações de sincronização planejadas.
    Retorna (sucessos, falhas).
    """
    success = 0
    failed = 0
    total = len(differences)

    for idx, diff in enumerate(differences, start=1):
        try:
            if diff.action_type == "copy_to_dst" and diff.src_path and diff.dst_path:
                diff.dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(diff.src_path), str(diff.dst_path))
                diff.status = "Copiado para Destino"
                success += 1
            elif diff.action_type == "copy_to_src" and diff.src_path and diff.dst_path:
                diff.src_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(diff.dst_path), str(diff.src_path))
                diff.status = "Copiado para Origem"
                success += 1
            elif diff.action_type == "delete_dst" and diff.dst_path:
                if diff.dst_path.exists():
                    diff.dst_path.unlink()
                diff.status = "Removido do Destino"
                success += 1
            elif diff.action_type in ("identical", "skip"):
                diff.status = "Ignorado"
            else:
                diff.status = "Ignorado"
        except Exception as e:
            diff.status = "Erro"
            diff.error = str(e)
            failed += 1

        if progress_cb:
            progress_cb(idx, total, f"Processado: {diff.rel_path.name}")

    return success, failed
