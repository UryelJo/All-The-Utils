"""
Lógica pura do Organizador Automático de Pastas (Auto Folder Organizer).
Desacoplada de interface gráfica, com suporte a simulação prévia (Dry-Run).
"""
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Callable, Dict, List, Optional, Tuple

DEFAULT_CATEGORIES: Dict[str, List[str]] = {
    "Imagens": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".svg", ".ico", ".raw", ".psd"],
    "Vídeos": [".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv", ".webm", ".m4v"],
    "Áudios": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".wma", ".m4a"],
    "Documentos": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".odt", ".rtf", ".epub"],
    "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"],
    "Código": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sql", ".cpp", ".c", ".h", ".cs", ".java", ".php", ".sh", ".ps1"],
    "Instaladores": [".exe", ".msi"],
}

MONTH_NAMES = [
    "01 - Janeiro", "02 - Fevereiro", "03 - Março", "04 - Abril",
    "05 - Maio", "06 - Junho", "07 - Julho", "08 - Agosto",
    "09 - Setembro", "10 - Outubro", "11 - Novembro", "12 - Dezembro"
]


@dataclass
class OrganizeAction:
    source_path: Path
    dest_path: Path
    category_label: str
    status: str = "Pendente"
    error: Optional[str] = None


def get_category_for_extension(ext: str, custom_categories: Optional[Dict[str, List[str]]] = None) -> str:
    """Identifica a categoria de uma extensão de arquivo."""
    cats = custom_categories or DEFAULT_CATEGORIES
    norm_ext = ext.lower()
    for cat_name, extensions in cats.items():
        if norm_ext in extensions:
            return cat_name
    return "Outros"


def plan_organization(
    folder: Path,
    mode: str = "category",
    recursive: bool = False,
    target_base_dir: Optional[Path] = None,
    custom_categories: Optional[Dict[str, List[str]]] = None,
) -> List[OrganizeAction]:
    """
    Simula e planeja a organização dos arquivos sem mover fisicamente nada no disco (Dry-Run).
    Modos: 'category', 'extension', 'date_month', 'date_year'.
    """
    folder = Path(folder).resolve()
    base_out = Path(target_base_dir).resolve() if target_base_dir else folder

    if not folder.is_dir():
        return []

    actions: List[OrganizeAction] = []
    iterator = folder.rglob("*") if recursive else folder.glob("*")

    for p in iterator:
        if not p.is_file():
            continue

        # Evita re-organizar arquivos que já estão dentro de subpastas do destino
        if base_out in p.parents and p.parent != folder:
            continue

        ext = p.suffix.lower()
        subfolder_name = ""
        reason = ""

        if mode == "category":
            subfolder_name = get_category_for_extension(ext, custom_categories)
            reason = f"Categoria: {subfolder_name}"
        elif mode == "extension":
            clean_ext = ext.lstrip(".").upper() or "SEM_EXTENSAO"
            subfolder_name = clean_ext
            reason = f"Extensão: {clean_ext}"
        elif mode == "date_month":
            try:
                mtime = p.stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                subfolder_name = f"{dt.year}/{MONTH_NAMES[dt.month - 1]}"
                reason = f"Modificado em {dt.strftime('%d/%m/%Y')}"
            except Exception:
                subfolder_name = "Data_Desconhecida"
                reason = "Data inacessível"
        elif mode == "date_year":
            try:
                mtime = p.stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                subfolder_name = str(dt.year)
                reason = f"Ano: {dt.year}"
            except Exception:
                subfolder_name = "Ano_Desconhecido"
                reason = "Data inacessível"
        else:
            subfolder_name = "Geral"
            reason = "Padrão"

        target_dir = base_out / subfolder_name
        dest_file = target_dir / p.name

        # Não planeja ação se o arquivo já estiver exatamente no destino previsto
        if p == dest_file:
            continue

        actions.append(
            OrganizeAction(
                source_path=p,
                dest_path=dest_file,
                category_label=reason,
            )
        )

    return actions


def execute_organization(
    actions: List[OrganizeAction],
    move_files: bool = True,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[int, int]:
    """
    Executa fisicamente as ações planejadas (mover ou copiar) com resolução de conflitos.
    Retorna tupla (sucessos, falhas).
    """
    success_count = 0
    fail_count = 0
    total = len(actions)

    for idx, act in enumerate(actions, start=1):
        src = act.source_path
        dst = act.dest_path

        try:
            if not src.exists():
                act.status = "Erro"
                act.error = "Origem não encontrada"
                fail_count += 1
                continue

            # Garante que o diretório de destino exista
            dst.parent.mkdir(parents=True, exist_ok=True)

            # Resolução de conflito de nome
            final_dst = dst
            if final_dst.exists() and final_dst != src:
                stem = dst.stem
                ext = dst.suffix
                counter = 1
                while final_dst.exists():
                    final_dst = dst.parent / f"{stem} ({counter}){ext}"
                    counter += 1

            if move_files:
                shutil.move(str(src), str(final_dst))
                act.dest_path = final_dst
                act.status = "Movido"
            else:
                shutil.copy2(str(src), str(final_dst))
                act.dest_path = final_dst
                act.status = "Copiado"

            success_count += 1
        except Exception as e:
            act.status = "Erro"
            act.error = str(e)
            fail_count += 1

        if progress_cb:
            progress_cb(idx, total, f"Processado: {src.name}")

    return success_count, fail_count
