"""
Lógica pura do Monitor de Pastas em Tempo Real (Folder Watcher).
Detecta arquivos criados, modificados e excluídos através de diferencial de snapshot contínuo de alta eficiência.
"""
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import time
from typing import Callable, Dict, List, Optional, Set, Tuple


@dataclass
class FolderWatchEvent:
    timestamp: str
    event_type: str  # "Criado", "Modificado", "Excluído"
    path: Path
    details: str


def take_directory_snapshot(folder: Path, recursive: bool = True) -> Dict[Path, Tuple[float, int]]:
    """
    Coleta o estado atual (mtime, size) de todos os arquivos de um diretório.
    """
    snapshot: Dict[Path, Tuple[float, int]] = {}
    folder = Path(folder).resolve()

    if not folder.is_dir():
        return snapshot

    try:
        iterator = folder.rglob("*") if recursive else folder.glob("*")
        for p in iterator:
            try:
                if p.is_file():
                    st = p.stat()
                    snapshot[p] = (st.st_mtime, st.st_size)
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass

    return snapshot


def compute_snapshot_diff(
    old_snap: Dict[Path, Tuple[float, int]],
    new_snap: Dict[Path, Tuple[float, int]],
) -> List[FolderWatchEvent]:
    """
    Compara dois snapshots e identifica arquivos criados, modificados e excluídos.
    """
    events: List[FolderWatchEvent] = []
    now_str = datetime.now().strftime("%H:%M:%S")

    old_keys = set(old_snap.keys())
    new_keys = set(new_snap.keys())

    # 1. Arquivos criados
    for p in new_keys - old_keys:
        events.append(
            FolderWatchEvent(
                timestamp=now_str,
                event_type="Criado",
                path=p,
                details=f"Novo arquivo ({new_snap[p][1]} bytes)"
            )
        )

    # 2. Arquivos excluídos
    for p in old_keys - new_keys:
        events.append(
            FolderWatchEvent(
                timestamp=now_str,
                event_type="Excluído",
                path=p,
                details="Arquivo removido"
            )
        )

    # 3. Arquivos modificados
    for p in old_keys & new_keys:
        old_mtime, old_size = old_snap[p]
        new_mtime, new_size = new_snap[p]
        if old_mtime != new_mtime or old_size != new_size:
            events.append(
                FolderWatchEvent(
                    timestamp=now_str,
                    event_type="Modificado",
                    path=p,
                    details=f"Tamanho: {old_size} -> {new_size} bytes"
                )
            )

    return events


def format_events_as_csv(events: List[FolderWatchEvent]) -> str:
    """Exporta lista de eventos em formato CSV delimitado por ponto e vírgula."""
    lines = ["Data/Hora;Evento;Arquivo;Caminho Completo;Detalhes"]
    for ev in events:
        lines.append(f"{ev.timestamp};{ev.event_type};{ev.path.name};{str(ev.path)};{ev.details}")
    return "\n".join(lines)
