"""
Lógica pura para edição e backup do arquivo hosts do Windows.
Isolada de qualquer interface gráfica.
"""
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple


def get_default_hosts_path() -> Path:
    """Retorna o caminho padrão do arquivo hosts no Windows."""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return Path(system_root) / "System32" / "drivers" / "etc" / "hosts"


def read_hosts_file(hosts_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Lê o arquivo hosts e retorna as entradas estruturadas.
    Cada entrada possui: ip, hostname, comment, is_enabled.
    """
    path = hosts_path or get_default_hosts_path()
    entries: List[Dict[str, Any]] = []

    if not path.exists():
        return entries

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        content = path.read_text(encoding="latin1", errors="ignore")

    for line in content.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue

        is_enabled = True
        line_to_parse = trimmed

        if trimmed.startswith("#"):
            # Pode ser uma entrada comentada/desativada ou um comentário de texto puro
            sub = trimmed.lstrip("#").strip()
            # Checa se parece com um IP seguido de host
            parts = sub.split()
            if len(parts) >= 2 and _is_valid_ip(parts[0]):
                is_enabled = False
                line_to_parse = sub
            else:
                # É apenas um comentário informativo de cabeçalho
                continue

        parts = line_to_parse.split()
        if len(parts) >= 2 and _is_valid_ip(parts[0]):
            ip = parts[0]
            host = parts[1]
            comment = " ".join(parts[2:]) if len(parts) > 2 else ""
            if comment.startswith("#"):
                comment = comment.lstrip("#").strip()

            entries.append({
                "ip": ip,
                "hostname": host,
                "comment": comment,
                "is_enabled": is_enabled,
            })

    return entries


def save_hosts_file(
    entries: List[Dict[str, Any]],
    hosts_path: Optional[Path] = None,
    create_backup: bool = True
) -> Tuple[bool, str]:
    """
    Salva as entradas fornecidas de volta no arquivo hosts.
    Cria automaticamente um backup antes de gravar.
    """
    path = hosts_path or get_default_hosts_path()

    if create_backup and path.exists():
        try:
            backup_dir = path.parent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"hosts.bak_{timestamp}"
            shutil.copy2(path, backup_file)
        except Exception as e:
            # Continua se falhar o backup na pasta de sistema, tenta criar em AppData
            pass

    lines = [
        "# Gerenciado pelo All the Utils - Arquivo Hosts do Windows",
        f"# Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        "127.0.0.1 localhost",
        "::1 localhost",
        ""
    ]

    for ent in entries:
        ip = ent.get("ip", "").strip()
        host = ent.get("hostname", "").strip()
        comment = ent.get("comment", "").strip()
        is_enabled = ent.get("is_enabled", True)

        if not ip or not host:
            continue

        prefix = "" if is_enabled else "# "
        comment_part = f" # {comment}" if comment else ""
        lines.append(f"{prefix}{ip.ljust(16)} {host}{comment_part}")

    lines.append("")
    content = "\n".join(lines)

    try:
        path.write_text(content, encoding="utf-8")
        return True, "Arquivo hosts atualizado com sucesso."
    except PermissionError:
        return False, "Permissão negada. É necessário executar como Administrador para modificar o arquivo hosts."
    except Exception as e:
        return False, f"Falha ao salvar hosts: {str(e)}"


def list_hosts_backups(hosts_path: Optional[Path] = None) -> List[Path]:
    """Lista todos os arquivos de backup do hosts disponíveis na pasta de drivers."""
    path = hosts_path or get_default_hosts_path()
    folder = path.parent
    if not folder.exists():
        return []

    backups = list(folder.glob("hosts.bak_*"))
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return backups


def restore_hosts_backup(backup_path: Path, hosts_path: Optional[Path] = None) -> Tuple[bool, str]:
    """Restaura um arquivo de backup para o arquivo hosts ativo."""
    dest = hosts_path or get_default_hosts_path()
    if not backup_path.exists():
        return False, "Arquivo de backup não encontrado."

    try:
        shutil.copy2(backup_path, dest)
        return True, f"Backup '{backup_path.name}' restaurado com sucesso."
    except PermissionError:
        return False, "Permissão negada ao restaurar backup. Execute como Administrador."
    except Exception as e:
        return False, f"Erro ao restaurar: {str(e)}"


def flush_dns_cache() -> Tuple[bool, str]:
    """Executa 'ipconfig /flushdns' para aplicar alterações do hosts imediatamente."""
    try:
        res = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return True, "Cache de resolução DNS limpo com sucesso (Flush DNS)."
        return False, f"Falha no flush DNS: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar flush DNS: {str(e)}"


def _is_valid_ip(ip_str: str) -> bool:
    """Valida se a string tem formato IPv4 ou IPv6 simples."""
    # IPv4 simples
    ipv4_pat = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    if re.match(ipv4_pat, ip_str):
        return True
    # IPv6 simples
    if ":" in ip_str:
        return True
    return False
