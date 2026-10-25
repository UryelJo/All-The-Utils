"""
Lógica pura da ferramenta Mover Pasta com Junção NTFS (junction_mover).
Transfere diretórios com segurança, valida integridade e cria junções NTFS sem perda de dados.
"""
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Dict, Optional, Tuple

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def is_reparse_point(path: Path) -> bool:
    """Verifica se o caminho informado é uma junção NTFS ou link simbólico."""
    try:
        path = Path(path)
        if not path.exists():
            return False
        if os.path.islink(path):
            return True
        st = os.stat(path, follow_symlinks=False)
        return bool(st.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def get_junction_target(path: Path) -> Optional[str]:
    """Obtém o destino para o qual a junção aponta, se aplicável."""
    try:
        return os.readlink(Path(path))
    except Exception:
        return None


def calculate_dir_size(path: Path) -> Tuple[int, int]:
    """Retorna (total_bytes, total_arquivos) de um diretório recursivamente."""
    total_bytes = 0
    total_files = 0
    path = Path(path)
    if not path.is_dir() or is_reparse_point(path):
        return 0, 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            try:
                total_bytes += fp.stat(follow_symlinks=False).st_size
                total_files += 1
            except (OSError, PermissionError):
                pass
    return total_bytes, total_files


def get_drive_free_space(path: Path) -> int:
    """Retorna o espaço livre em bytes no disco correspondente ao caminho."""
    try:
        path = Path(path)
        anchor = path.anchor or str(path)
        return shutil.disk_usage(anchor).free
    except Exception:
        return 0


def create_ntfs_junction(link_path: Path, target_path: Path) -> bool:
    """
    Cria uma junção NTFS (Directory Junction).
    Não requer privilégios de Administrador no Windows.
    """
    link_p = Path(link_path).resolve()
    target_p = Path(target_path).resolve()

    try:
        import _winapi
        _winapi.CreateJunction(str(target_p), str(link_p))
        return is_reparse_point(link_p)
    except Exception:
        pass

    # Fallback via comando nativo mklink /J
    try:
        flags = 0x08000000 if os.name == "nt" else 0
        cmd = ["cmd.exe", "/c", "mklink", "/J", str(link_p), str(target_p)]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags
        )
        return res.returncode == 0 and is_reparse_point(link_p)
    except Exception:
        return False


def validate_move_junction(source_dir: str | Path, target_dir: str | Path) -> Tuple[bool, str]:
    """
    Valida preventivamente se a movimentação e junção podem ser executadas com segurança.
    """
    src = Path(source_dir).resolve()
    dst = Path(target_dir).resolve()

    if not src.exists():
        return False, f"A pasta de origem '{src}' não existe."
    if not src.is_dir():
        return False, f"O caminho de origem '{src}' não é um diretório."
    if is_reparse_point(src):
        return False, f"A pasta de origem '{src}' já é uma junção ou atalho NTFS existente."
    if src == dst:
        return False, "A pasta de origem e a de destino não podem ser a mesma."

    # Previne recursão infinita (destino dentro da origem ou vice-versa)
    try:
        dst.relative_to(src)
        return False, f"A pasta de destino '{dst}' está dentro da pasta de origem '{src}', o que causaria recursão infinita."
    except ValueError:
        pass

    try:
        src.relative_to(dst)
        return False, f"A pasta de origem '{src}' está dentro da pasta de destino '{dst}'."
    except ValueError:
        pass

    if dst.exists() and any(dst.iterdir()):
        return False, f"A pasta de destino '{dst}' já existe e contém arquivos. O destino deve estar vazio ou não existir."

    total_bytes, _ = calculate_dir_size(src)
    free_bytes = get_drive_free_space(dst.parent if not dst.exists() else dst)

    if free_bytes < (total_bytes + 50 * 1024 * 1024):
        needed_mb = round(total_bytes / (1024 * 1024), 1)
        avail_mb = round(free_bytes / (1024 * 1024), 1)
        return False, f"Espaço insuficiente no disco de destino: {avail_mb} MB disponíveis (necessários: {needed_mb} MB + 50 MB de margem)."

    return True, "Validação concluída com sucesso."


def move_folder_and_create_junction(
    source_dir: Path,
    target_dir: Path,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Copia os dados para o destino de forma transacional e cria uma Junção NTFS.
    Fluxo Seguro:
      1. Validação estrita contra recursão e espaço em disco.
      2. Cópia completa para o destino (com robocopy se disponível, preservando atributos e permissões).
      3. Renomeação segura da origem para ._wtbx_bak (não apaga nada antes da junção existir).
      4. Criação da junção em 'src' apontando para 'dst'.
      5. Em caso de falha na criação da junção, executa ROLLBACK imediato revertendo o nome da origem.
      6. Somente após confirmação de funcionamento da junção, o backup da origem é descartado.
    """
    src = Path(source_dir).resolve()
    dst = Path(target_dir).resolve()

    valid, msg = validate_move_junction(src, dst)
    if not valid:
        raise ValueError(msg)

    total_bytes, total_files = calculate_dir_size(src)

    if progress_cb:
        progress_cb(5, "Preparando estrutura de destino...")

    dst.mkdir(parents=True, exist_ok=True)

    # 1. Copiar arquivos: prioriza Robocopy nativo no Windows (rápido, multi-thread, preserva atributos)
    copied_files = 0
    copied_bytes = 0
    robocopy_exe = shutil.which("robocopy.exe") or shutil.which("robocopy")

    use_robocopy = (os.name == "nt" and robocopy_exe is not None)

    if use_robocopy:
        if progress_cb:
            progress_cb(15, "Copiando arquivos via Robocopy nativo (multi-thread)...")
        flags = 0x08000000
        # Robocopy: /E = recursivo com vazias, /COPY:DAT = dados/atributos/timestamps, /DCOPY:DAT, /XJ = exclui junções para evitar loops
        # /R:1 /W:1 = 1 retry de 1 seg, /MT:8 = 8 threads
        cmd = [
            robocopy_exe,
            str(src),
            str(dst),
            "/E",
            "/COPY:DAT",
            "/DCOPY:DAT",
            "/XJ",
            "/R:1",
            "/W:1",
            "/MT:8",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags)
        # Códigos 0 a 7 no robocopy indicam sucesso
        if res.returncode >= 8:
            raise RuntimeError(f"Robocopy falhou com código {res.returncode}:\n{res.stderr or res.stdout}")
        copied_bytes, copied_files = calculate_dir_size(dst)
    else:
        # Fallback padrão via Python
        for root, dirs, files in os.walk(src):
            rel_path = Path(root).relative_to(src)
            target_sub = dst / rel_path
            target_sub.mkdir(parents=True, exist_ok=True)

            for d in dirs:
                (target_sub / d).mkdir(parents=True, exist_ok=True)

            for f in files:
                s_file = Path(root) / f
                d_file = target_sub / f
                try:
                    shutil.copy2(s_file, d_file)
                    f_size = s_file.stat(follow_symlinks=False).st_size
                    copied_bytes += f_size
                    copied_files += 1
                    if progress_cb and total_files > 0:
                        pct = int(15 + (copied_files / total_files) * 65)
                        progress_cb(pct, f"Copiando: {f}")
                except Exception as err:
                    raise RuntimeError(f"Falha ao copiar '{s_file.name}': {err}")

    if progress_cb:
        progress_cb(82, "Validando integridade dos arquivos copiados...")

    dst_bytes, dst_files = calculate_dir_size(dst)
    if dst_files < total_files:
        raise RuntimeError(
            f"A conferência falhou: {dst_files} arquivos encontrados no destino contra {total_files} na origem."
        )

    # 2. Transação segura: Renomear origem para pasta de backup temporária
    backup_src = src.with_name(f"{src.name}._wtbx_bak")
    if backup_src.exists():
        if is_reparse_point(backup_src):
            backup_src.unlink()
        else:
            shutil.rmtree(backup_src, ignore_errors=True)

    if progress_cb:
        progress_cb(88, "Criando ponto de isolamento transacional...")

    try:
        src.rename(backup_src)
    except Exception as err:
        raise RuntimeError(
            f"Não foi possível mover a pasta de origem para isolamento (arquivo em uso ou sem permissão): {err}"
        )

    # 3. Criar a junção em 'src' apontando para 'dst'
    if progress_cb:
        progress_cb(92, "Criando Junção NTFS (Directory Junction)...")

    junction_created = False
    try:
        junction_created = create_ntfs_junction(src, dst)
    except Exception:
        junction_created = False

    if not junction_created:
        # ROLLBACK IMEDIATO: restaura a origem e lança erro
        if progress_cb:
            progress_cb(94, "Erro na criação da junção. Executando Rollback...")
        if backup_src.exists() and not src.exists():
            backup_src.rename(src)
        raise RuntimeError(
            f"Falha ao criar a junção NTFS no caminho '{src}'. A pasta de origem foi restaurada intacta (Rollback)."
        )

    # 4. Sucesso confirmado: Agora pode descartar com segurança a pasta de backup
    if progress_cb:
        progress_cb(96, "Limpando arquivos temporários da origem...")

    try:
        shutil.rmtree(backup_src, ignore_errors=True)
    except Exception:
        pass

    if progress_cb:
        progress_cb(100, "Junção NTFS criada com sucesso!")

    return {
        "success": True,
        "source": str(src),
        "target": str(dst),
        "total_files": dst_files,
        "total_bytes": dst_bytes,
    }
