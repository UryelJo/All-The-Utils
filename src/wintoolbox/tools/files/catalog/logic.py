"""
Lógica pura para indexação e catalogação de diretórios e mídias externas.
Permite criar snapshots leves da estrutura de arquivos e pastas para busca offline instantânea.

Zero dependências de interface gráfica ou widgets.
"""
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def format_bytes(size: int) -> str:
    """Formata bytes para representação legível (B, KB, MB, GB)."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def scan_directory_catalog(
    root_path: str,
    catalog_name: Optional[str] = None,
    max_entries: int = 500_000,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """
    Escaneia recursivamente um diretório e gera uma estrutura de catálogo para buscas offline.
    """
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Caminho não encontrado: {root_path}")

    cat_name = catalog_name or root.name or str(root)
    entries: List[Dict[str, Any]] = []

    total_files = 0
    total_dirs = 0
    total_bytes = 0

    # os.walk para máxima performance no Windows
    for dirpath, dirnames, filenames in os.walk(str(root)):
        if len(entries) >= max_entries:
            break

        rel_dir = os.path.relpath(dirpath, str(root))
        if rel_dir == ".":
            rel_dir = ""

        total_dirs += len(dirnames)

        for fname in filenames:
            if len(entries) >= max_entries:
                break

            total_files += 1
            full_path = os.path.join(dirpath, fname)
            rel_file = os.path.join(rel_dir, fname) if rel_dir else fname

            size = 0
            mtime = 0.0
            try:
                st = os.stat(full_path)
                size = st.st_size
                mtime = st.st_mtime
            except OSError:
                pass

            total_bytes += size
            ext = os.path.splitext(fname)[1].lower()

            entries.append({
                "path": rel_file.replace("\\", "/"),
                "name": fname,
                "size": size,
                "mtime": mtime,
                "ext": ext,
            })

            if progress_callback and total_files % 1000 == 0:
                progress_callback(total_files)

    return {
        "catalog_name": cat_name,
        "root_path": str(root),
        "created_at": datetime.now().isoformat(),
        "total_files": total_files,
        "total_dirs": total_dirs,
        "total_bytes": total_bytes,
        "total_bytes_formatted": format_bytes(total_bytes),
        "entries": entries,
    }


def save_catalog_to_file(catalog_data: Dict[str, Any], output_path: str) -> None:
    """Salva dados do catálogo em arquivo JSON formatado."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, ensure_ascii=False, indent=2)


def load_catalog_from_file(catalog_path: str) -> Dict[str, Any]:
    """Carrega catálogo salvo em arquivo JSON."""
    p = Path(catalog_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo de catálogo não encontrado: {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError("Arquivo de catálogo inválido ou corrompido.")

    return data


def search_catalog_entries(
    catalog_data: Dict[str, Any],
    query: str = "",
    extension: str = "",
    min_size_bytes: int = 0,
    max_size_bytes: int = 0,
) -> List[Dict[str, Any]]:
    """
    Busca rápida em memória sobre as entradas de um catálogo de arquivos offline.
    """
    entries = catalog_data.get("entries", [])
    needle = query.lower().strip()
    target_ext = extension.lower().strip()
    if target_ext and not target_ext.startswith("."):
        target_ext = f".{target_ext}"

    results: List[Dict[str, Any]] = []

    for item in entries:
        # Filtro de extensão
        if target_ext and item.get("ext") != target_ext:
            continue

        # Filtro de tamanho
        size = item.get("size", 0)
        if min_size_bytes > 0 and size < min_size_bytes:
            continue
        if max_size_bytes > 0 and size > max_size_bytes:
            continue

        # Filtro de texto no nome ou caminho
        if needle:
            name = item.get("name", "").lower()
            path = item.get("path", "").lower()
            if needle not in name and needle not in path:
                continue

        item_copy = dict(item)
        item_copy["size_formatted"] = format_bytes(size)
        if item.get("mtime"):
            item_copy["mtime_formatted"] = datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        else:
            item_copy["mtime_formatted"] = ""

        results.append(item_copy)

    return results
