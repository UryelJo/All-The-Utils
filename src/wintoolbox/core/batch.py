"""
Motor Central de Processamento em Lote (Batch Engine).
Responsável por descoberta de arquivos, filtragem, políticas de saída,
espelhamento de pastas, execução segura e relatórios.
"""
import os
import time
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import ItemResult, TaskContext, ToolResult

_log = get_logger("batch")

@dataclass
class SourceItem:
    path: Path
    is_dir: bool
    recursive: bool = False

@dataclass
class OutputPolicy:
    mode: str = "subfolder"  # 'subfolder', 'custom', 'same_folder'
    subfolder_name: str = "convertidos"
    custom_dir: Optional[Path] = None
    mirror_structure: bool = True
    naming_pattern: str = "{name}"  # Suporta {name}, {ext}, {date}, etc.
    conflict: str = "rename"  # 'rename', 'overwrite', 'skip'
    preserve_timestamps: bool = True

@dataclass
class DiscoveredFile:
    """Arquivo descoberto pronto para processamento."""
    source_path: Path
    root_source_dir: Optional[Path] = None  # Diretório base quando veio de uma pasta
    size_bytes: int = 0
    extension: str = ""

def discover_files(
    sources: List[SourceItem],
    allowed_extensions: Optional[Set[str]] = None,
    on_file_found: Optional[Callable[[DiscoveredFile], None]] = None
) -> List[DiscoveredFile]:
    """
    Realiza a varredura rápida de todos os itens de entrada.
    Suporta arquivos individuais e pastas (recursivas ou não).
    """
    discovered: List[DiscoveredFile] = []
    seen_paths: Set[Path] = set()

    # Normaliza extensões permitidas para minúsculas
    norm_exts = {ext.lower() if ext.startswith('.') else f".{ext.lower()}" for ext in allowed_extensions} if allowed_extensions else None

    for item in sources:
        p = item.path.resolve()
        if not p.exists():
            continue

        if not item.is_dir and p.is_file():
            ext = p.suffix.lower()
            if norm_exts is None or ext in norm_exts:
                if p not in seen_paths:
                    seen_paths.add(p)
                    df = DiscoveredFile(
                        source_path=p,
                        root_source_dir=p.parent,
                        size_bytes=p.stat().st_size,
                        extension=ext
                    )
                    discovered.append(df)
                    if on_file_found:
                        on_file_found(df)
        elif item.is_dir and p.is_dir():
            if item.recursive:
                for root, _, files in os.walk(p):
                    root_path = Path(root)
                    for fname in files:
                        fp = root_path / fname
                        ext = fp.suffix.lower()
                        if norm_exts is None or ext in norm_exts:
                            if fp not in seen_paths:
                                seen_paths.add(fp)
                                try:
                                    sz = fp.stat().st_size
                                except Exception:
                                    sz = 0
                                df = DiscoveredFile(
                                    source_path=fp,
                                    root_source_dir=p,
                                    size_bytes=sz,
                                    extension=ext
                                )
                                discovered.append(df)
                                if on_file_found:
                                    on_file_found(df)
            else:
                try:
                    with os.scandir(p) as it:
                        for entry in it:
                            if entry.is_file():
                                fp = Path(entry.path)
                                ext = fp.suffix.lower()
                                if norm_exts is None or ext in norm_exts:
                                    if fp not in seen_paths:
                                        seen_paths.add(fp)
                                        try:
                                            sz = entry.stat().st_size
                                        except Exception:
                                            sz = 0
                                        df = DiscoveredFile(
                                            source_path=fp,
                                            root_source_dir=p,
                                            size_bytes=sz,
                                            extension=ext
                                        )
                                        discovered.append(df)
                                        if on_file_found:
                                            on_file_found(df)
                except Exception:
                    pass

    return discovered

def calculate_destination_path(
    item: DiscoveredFile,
    output_policy: OutputPolicy,
    target_ext: str,
    extra_vars: Optional[Dict[str, str]] = None,
    reserved: Optional[Set[str]] = None
) -> Path:
    """
    Calcula o caminho de destino exato para um item baseado na política de saída,
    espelhamento relativo de subpastas e resolução de conflitos de nome.
    """
    src = item.source_path
    if not target_ext:
        # Ferramentas que preservam o formato (redimensionar, comprimir...) retornam ""
        target_ext = src.suffix
    elif not target_ext.startswith('.'):
        target_ext = f".{target_ext}"

    # 1. Determina a pasta base de destino
    if output_policy.mode == "same_folder":
        base_dest = src.parent
    elif output_policy.mode == "subfolder":
        sub_name = output_policy.subfolder_name.strip() or "convertidos"
        base_dest = src.parent / sub_name
    elif output_policy.mode == "custom" and output_policy.custom_dir:
        base_dest = output_policy.custom_dir.resolve()
        # Se espelhamento estiver ativado e o arquivo veio de uma pasta
        if output_policy.mirror_structure and item.root_source_dir:
            try:
                rel_dir = src.parent.relative_to(item.root_source_dir)
                base_dest = base_dest / rel_dir
            except ValueError:
                pass
    else:
        base_dest = src.parent

    # 2. Formata o nome do arquivo
    variables = {
        "name": src.stem,
        "ext": target_ext.lstrip('.'),
        "old_ext": src.suffix.lstrip('.'),
        "date": time.strftime("%Y%m%d")
    }
    if extra_vars:
        variables.update(extra_vars)

    formatted_name = output_policy.naming_pattern
    for k, v in variables.items():
        formatted_name = formatted_name.replace(f"{{{k}}}", str(v))

    target_filename = f"{formatted_name}{target_ext}"
    final_path = base_dest / target_filename

    # 3. Resolução de conflitos (inclui destinos já reservados por outros itens do lote)
    def _taken(p: Path) -> bool:
        return p.exists() or (reserved is not None and _norm_key(p) in reserved)

    if output_policy.conflict == "rename" and _taken(final_path):
        counter = 1
        while _taken(final_path):
            final_path = base_dest / f"{formatted_name} ({counter}){target_ext}"
            counter += 1

    if reserved is not None:
        reserved.add(_norm_key(final_path))
    return final_path


def _norm_key(p: Path) -> str:
    """Chave de comparação de caminhos insensível a maiúsculas (NTFS)."""
    return os.path.normcase(str(p))

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


def execute_batch(
    files: List[DiscoveredFile],
    output_policy: OutputPolicy,
    target_ext: str,
    process_func: Callable[[Path, Path, Dict, TaskContext], ItemResult],
    params: Dict,
    ctx: TaskContext,
    max_workers: Optional[int] = None,
    parallel_mode: str = "thread",
) -> ToolResult:
    """
    Executa o lote com suporte a concorrência paralela multi-core, cancelamento e progresso.
    """
    total = len(files)
    if total == 0:
        return ToolResult(success=True, message="Nenhum arquivo para processar.")

    if max_workers is None or max_workers <= 0:
        try:
            from wintoolbox.core.hardware import get_hardware_capabilities
            max_workers = get_hardware_capabilities().optimal_batch_workers
        except Exception:
            max_workers = min(os.cpu_count() or 4, 8)

    # Força modo serial se a ferramenta for explicitamente serial ou tiver apenas 1 arquivo
    if parallel_mode == "serial" or total == 1 or max_workers <= 1:
        workers = 1
    else:
        workers = min(max_workers, total)

    results: List[ItemResult] = []
    success_count = 0
    failed_count = 0
    skipped_count = 0
    completed_count = 0
    lock = threading.Lock()
    reserved: Set[str] = set()

    ctx.on_progress(0, total, f"Iniciando lote ({total} itens, {workers} worker(s) em paralelo)...")

    def _process_single(item: DiscoveredFile) -> ItemResult:
        nonlocal success_count, failed_count, skipped_count, completed_count

        if ctx.is_cancelled():
            return ItemResult(success=False, source_path=item.source_path, error="Operação cancelada.")

        while ctx.is_paused() and not ctx.is_cancelled():
            time.sleep(0.2)

        src = item.source_path
        with lock:
            # Reserva o destino sob lock: dois itens paralelos (ex: foto.png e foto.jpg -> foto.webp)
            # não podem receber o mesmo caminho.
            already_reserved = _norm_key(calculate_destination_path(item, output_policy, target_ext)) in reserved
            dst = calculate_destination_path(item, output_policy, target_ext, reserved=reserved)

        # Política de pular arquivo existente
        if output_policy.conflict == "skip" and (dst.exists() or already_reserved):
            with lock:
                skipped_count += 1
                completed_count += 1
                res = ItemResult(success=True, source_path=src, output_path=dst, message="Ignorado (já existe)")
                results.append(res)
                ctx.on_log("INFO", f"Ignorado (já existe): {src.name}")
                ctx.on_progress(completed_count, total, f"Ignorado {completed_count}/{total}: {src.name}")
            return res

        # Garante diretório de destino
        dst.parent.mkdir(parents=True, exist_ok=True)
        # O temporário mantém a extensão final: Pillow, ffmpeg e o Office deduzem o formato por ela
        tmp_dst = dst.with_name(f"{dst.stem}.wtbx-{os.getpid()}-{threading.get_ident()}.tmp{dst.suffix}")

        try:
            res = process_func(src, tmp_dst, params, ctx)
            # Ferramentas que geram várias saídas (ex: extrator de quadros) escrevem em output_path
            wrote_elsewhere = (
                res.success and not tmp_dst.exists()
                and res.output_path is not None and Path(res.output_path).exists()
            )
            if res.success and (tmp_dst.exists() or wrote_elsewhere):
                if tmp_dst.exists():
                    if dst.exists() and output_policy.conflict != "overwrite":
                        raise FileExistsError(f"Destino já existe: {dst}")
                    os.replace(tmp_dst, dst)
                    res.output_path = dst
                else:
                    dst = Path(res.output_path)

                if output_policy.preserve_timestamps and dst.is_file():
                    try:
                        stat = src.stat()
                        os.utime(dst, (stat.st_atime, stat.st_mtime))
                    except Exception:
                        pass

                with lock:
                    success_count += 1
                    completed_count += 1
                    results.append(res)
                    ctx.on_log("INFO", f"OK: {src.name} -> {dst.name}")
                    ctx.on_progress(completed_count, total, f"Processado {completed_count}/{total}: {src.name}")
            else:
                if tmp_dst.exists():
                    try:
                        tmp_dst.unlink()
                    except Exception:
                        pass
                with lock:
                    failed_count += 1
                    completed_count += 1
                    results.append(res)
                    ctx.on_log("ERROR", f"Falha: {src.name} ({res.error or 'Erro desconhecido'})")
                    ctx.on_progress(completed_count, total, f"Falha {completed_count}/{total}: {src.name}")
            return res
        except Exception as e:
            if tmp_dst.exists():
                try:
                    tmp_dst.unlink()
                except Exception:
                    pass
            with lock:
                failed_count += 1
                completed_count += 1
                res = ItemResult(success=False, source_path=src, error=str(e))
                results.append(res)
                ctx.on_log("ERROR", f"Exceção em {src.name}: {str(e)}")
                _log.exception("Exceção ao processar '%s' com %s", src, getattr(process_func, "__qualname__", process_func))
                ctx.on_progress(completed_count, total, f"Erro {completed_count}/{total}: {src.name}")
            return res

    if workers == 1:
        for it in files:
            if ctx.is_cancelled():
                ctx.on_log("WARN", "Operação cancelada pelo usuário.")
                break
            _process_single(it)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_process_single, it) for it in files]
            for fut in as_completed(futures):
                if ctx.is_cancelled():
                    break
                try:
                    fut.result()
                except Exception:
                    pass

    msg = f"Lote concluído ({workers} threads). Sucessos: {success_count} | Falhas: {failed_count} | Pulados: {skipped_count}"
    ctx.on_log("INFO", msg)

    return ToolResult(
        success=(failed_count == 0),
        message=msg,
        items_total=total,
        items_success=success_count,
        items_failed=failed_count,
        items_skipped=skipped_count,
        details=results
    )
