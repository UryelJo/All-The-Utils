"""
Lógica de execução das ferramentas de sistema e manutenção do Windows.
"""
import os
import shutil
from pathlib import Path
from typing import Callable, Dict

def clean_temp_directory(on_log: Callable[[str], None]) -> Dict[str, int]:
    """Limpa arquivos e diretórios dentro do %TEMP% do usuário."""
    temp_dir = os.environ.get("TEMP", "")
    if not temp_dir or not os.path.isdir(temp_dir):
        on_log("Diretório temporário (%TEMP%) não localizado.")
        return {"files": 0, "freed_mb": 0, "errors": 0}

    deleted_files = 0
    deleted_bytes = 0
    errors = 0

    on_log(f"Iniciando varredura em: {temp_dir}")
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                sz = os.path.getsize(file_path)
                os.remove(file_path)
                deleted_files += 1
                deleted_bytes += sz
            except Exception:
                errors += 1

        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
            except Exception:
                pass

    freed_mb = round(deleted_bytes / (1024 * 1024), 2)
    on_log(f"Limpeza finalizada: {deleted_files} arquivos removidos (~{freed_mb} MB liberados). {errors} arquivos em uso ignorados.")
    return {"files": deleted_files, "freed_mb": freed_mb, "errors": errors}
