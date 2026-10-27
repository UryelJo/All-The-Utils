"""
Lógica pura para construção de comandos, parse de argumentos e análise de saída do Robocopy do Windows.
Interpreta o código de saída em bitmask do Robocopy e sumários estatísticos.

Zero dependências de interface gráfica ou widgets.
"""
from pathlib import Path
import re
from typing import Any, Dict, List, Optional


def build_robocopy_command(
    source_dir: str,
    target_dir: str,
    mode: str = "mirror",  # 'mirror' (/MIR), 'all_subdirs' (/E), 'newer_only' (/XO /E)
    threads: int = 8,
    retry_count: int = 3,
    wait_seconds: int = 5,
    restartable: bool = True,  # /Z
    dry_run: bool = False,     # /L
    exclude_dirs: Optional[List[str]] = None,
    exclude_files: Optional[List[str]] = None,
    inter_packet_gap_ms: int = 0,  # /IPG
    log_file_path: Optional[str] = None,
) -> List[str]:
    """
    Constrói a lista de argumentos para execução do utilitário robocopy.exe.
    """
    cmd = ["robocopy", str(source_dir), str(target_dir)]

    # Modo de cópia
    if mode == "mirror":
        cmd.append("/MIR")
    elif mode == "newer_only":
        cmd.extend(["/E", "/XO"])
    elif mode == "all_subdirs":
        cmd.append("/E")

    # Multithreading (entre 1 e 128)
    if threads > 1:
        cmd.append(f"/MT:{min(128, max(1, threads))}")

    # Resiliência
    if restartable:
        cmd.append("/Z")

    cmd.append(f"/R:{max(0, retry_count)}")
    cmd.append(f"/W:{max(0, wait_seconds)}")

    # Simulação (Dry Run)
    if dry_run:
        cmd.append("/L")

    # Limite de banda
    if inter_packet_gap_ms > 0:
        cmd.append(f"/IPG:{inter_packet_gap_ms}")

    # Exclusões de diretórios
    if exclude_dirs:
        clean_dirs = [d.strip() for d in exclude_dirs if d.strip()]
        if clean_dirs:
            cmd.append("/XD")
            cmd.extend(clean_dirs)

    # Exclusões de arquivos
    if exclude_files:
        clean_files = [f.strip() for f in exclude_files if f.strip()]
        if clean_files:
            cmd.append("/XF")
            cmd.extend(clean_files)

    # Arquivo de log
    if log_file_path:
        cmd.append(f"/LOG:{log_file_path}")

    # Opções recomendadas para terminal amigável
    cmd.extend(["/NP", "/TEE"])

    return cmd


def parse_robocopy_exit_code(exit_code: int) -> Dict[str, Any]:
    """
    Analisa o código de saída em bitmask do Robocopy do Windows.
    Qualquer valor abaixo de 8 indica sucesso (com avisos ou arquivos copiados).
    Valores >= 8 indicam falhas sérias ou erros de I/O.
    """
    is_error = exit_code >= 8
    details: List[str] = []

    if exit_code == 0:
        details.append("Nenhum arquivo copiado (origem e destino já sincronizados).")
    if exit_code & 1:
        details.append("Um ou mais arquivos copiados com sucesso.")
    if exit_code & 2:
        details.append("Arquivos extras presentes no destino.")
    if exit_code & 4:
        details.append("Arquivos divergentes detectados.")
    if exit_code & 8:
        details.append("ERRO: Alguns arquivos ou pastas não puderam ser copiados (falha de permissão ou I/O).")
    if exit_code & 16:
        details.append("ERRO GRAVE: Falha grave de sintaxe ou parâmetros incorretos.")

    return {
        "exit_code": exit_code,
        "is_success": not is_error,
        "is_error": is_error,
        "summary": "Sucesso" if not is_error else "Falha no Robocopy",
        "details": details,
    }


def parse_robocopy_summary(output_text: str) -> Dict[str, Any]:
    """
    Extrai contagens de arquivos e bytes da tabela resumo final do Robocopy.
    """
    stats = {
        "dirs_total": 0,
        "dirs_copied": 0,
        "files_total": 0,
        "files_copied": 0,
        "bytes_total": 0,
        "bytes_copied": 0,
    }

    # Procura linha de 'Arquivos :' ou 'Files :'
    files_match = re.search(r"(?:Arquivos|Files)\s*:\s*(\d+)\s+(\d+)", output_text, re.IGNORECASE)
    if files_match:
        stats["files_total"] = int(files_match.group(1))
        stats["files_copied"] = int(files_match.group(2))

    # Procura linha de 'Pastas :' ou 'Dirs :'
    dirs_match = re.search(r"(?:Pastas|Dirs)\s*:\s*(\d+)\s+(\d+)", output_text, re.IGNORECASE)
    if dirs_match:
        stats["dirs_total"] = int(dirs_match.group(1))
        stats["dirs_copied"] = int(dirs_match.group(2))

    return stats
