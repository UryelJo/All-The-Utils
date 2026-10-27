"""
Lógica pura para agregação e consulta de status de múltiplos repositórios Git locais.
Executa comandos Git sem travar a interface e compila relatórios de branches e pendências.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class GitRepoInfo:
    """Representa o estado resumido de um repositório Git."""
    path: Path
    name: str
    current_branch: str
    is_dirty: bool
    modified_count: int
    untracked_count: int
    ahead_count: int
    behind_count: int
    last_commit_date: str
    last_commit_message: str


def run_git_cmd(repo_path: Path, args: List[str]) -> Tuple[int, str]:
    """Executa um comando git dentro do diretório do repositório."""
    git_bin = shutil.which("git") or "git"
    cmd = [git_bin] + args

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return proc.returncode, proc.stdout.strip()
    except Exception:
        return -1, ""


def get_repo_details(repo_path: Path) -> Optional[GitRepoInfo]:
    """Obtém o status de um repositório Git específico."""
    repo_path = Path(repo_path).resolve()
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return None

    # 1. Branch atual
    code, branch = run_git_cmd(repo_path, ["branch", "--show-current"])
    if code != 0 or not branch:
        code, branch = run_git_cmd(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if code != 0:
            branch = "HEAD Desanexado"

    # 2. Status de arquivos
    _, status_out = run_git_cmd(repo_path, ["status", "--porcelain"])
    modified = 0
    untracked = 0
    for line in status_out.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith("??"):
            untracked += 1
        else:
            modified += 1

    is_dirty = (modified > 0 or untracked > 0)

    # 3. Commits à frente e atrás do upstream
    code, count_out = run_git_cmd(repo_path, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
    ahead = 0
    behind = 0
    if code == 0 and "\t" in count_out:
        parts = count_out.split("\t")
        try:
            ahead = int(parts[0])
            behind = int(parts[1])
        except ValueError:
            pass

    # 4. Último commit
    _, log_out = run_git_cmd(repo_path, ["log", "-1", "--format=%cd||%s", "--date=relative"])
    date_str = ""
    msg_str = ""
    if "||" in log_out:
        date_str, msg_str = log_out.split("||", 1)

    return GitRepoInfo(
        path=repo_path,
        name=repo_path.name,
        current_branch=branch or "desconhecida",
        is_dirty=is_dirty,
        modified_count=modified,
        untracked_count=untracked,
        ahead_count=ahead,
        behind_count=behind,
        last_commit_date=date_str,
        last_commit_message=msg_str
    )


def scan_git_repositories(root_dir: Path, max_depth: int = 3) -> List[GitRepoInfo]:
    """Varre uma pasta raiz procurando diretórios com repositórios Git."""
    root_dir = Path(root_dir).resolve()
    if not root_dir.is_dir():
        raise FileNotFoundError(f"Diretório não encontrado: {root_dir}")

    repos: List[GitRepoInfo] = []

    def _walk(current: Path, depth: int):
        if depth > max_depth:
            return

        # Se esta pasta já é um repositório Git, analisa e não desce mais
        if (current / ".git").exists():
            info = get_repo_details(current)
            if info:
                repos.append(info)
            return

        try:
            for entry in os.scandir(current):
                if entry.is_dir(follow_symlinks=False):
                    name_lower = entry.name.lower()
                    if name_lower not in [".git", "node_modules", "target", "bin", "obj", "venv", ".venv"]:
                        _walk(Path(entry.path), depth + 1)
        except (OSError, PermissionError):
            pass

    _walk(root_dir, 1)
    repos.sort(key=lambda r: (not r.is_dirty, r.name.lower()))
    return repos
