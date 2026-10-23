"""
Lógica pura da ferramenta Renomeador de Arquivos em Lote (Batch Renamer).
Implementa regras de transformação de nomes e execução física no disco sem acoplamento a UI.
"""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, List, Optional


class RenameItem:
    def __init__(self, original_path: Path, new_name: Optional[str] = None, status: str = "Pendente"):
        self.original_path = original_path
        self.new_name = new_name if new_name is not None else original_path.name
        self.status = status


def compute_new_name(
    original_name: str,
    index: int = 0,
    find_str: str = "",
    replace_str: str = "",
    prefix: str = "",
    suffix: str = "",
    is_regex: bool = False,
    add_number: bool = False,
    start_num: int = 1,
    digits: int = 1,
    case_opt: str = "Manter Original",
) -> str:
    """Calcula o novo nome do arquivo a partir de regras empilhadas."""
    p = Path(original_name)
    stem = p.stem
    ext = p.suffix

    # 1. Localizar e substituir
    if find_str:
        if is_regex:
            try:
                stem = re.sub(find_str, replace_str, stem)
            except re.error:
                pass
        else:
            stem = stem.replace(find_str, replace_str)

    # 2. Prefixo e Sufixo
    if prefix:
        stem = f"{prefix}{stem}"
    if suffix:
        stem = f"{stem}{suffix}"

    # 3. Numeração
    if add_number:
        num_str = str(start_num + index).zfill(digits)
        stem = f"{stem}_{num_str}"

    # 4. Caixa
    if case_opt == "MAIÚSCULAS":
        stem = stem.upper()
    elif case_opt == "minúsculas":
        stem = stem.lower()
    elif case_opt == "Primeira Maiúscula":
        stem = stem.title()

    return f"{stem}{ext}"


def execute_batch_rename(
    items: List[RenameItem],
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> int:
    """Executa a renomeação física dos arquivos no disco."""
    total = len(items)
    success_count = 0

    for idx, item in enumerate(items):
        old_path = item.original_path
        new_path = old_path.parent / item.new_name
        if old_path != new_path:
            try:
                if new_path.exists():
                    item.status = "Erro: Já existe"
                else:
                    old_path.rename(new_path)
                    item.original_path = new_path
                    item.status = "Renomeado com sucesso"
                    success_count += 1
            except Exception as e:
                item.status = f"Erro: {str(e)}"
        else:
            item.status = "Sem alteração"

        if progress_cb and total > 0:
            progress_cb(int(((idx + 1) / total) * 100), item.new_name)

    return success_count
