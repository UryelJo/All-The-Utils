"""
Testes unitários para dev.git_overview.
Valida inspeção de repositórios Git reais criados em disco.
"""
import subprocess
import pytest
from pathlib import Path

from wintoolbox.tools.dev.git_overview.logic import (
    get_repo_details,
    scan_git_repositories,
)


@pytest.fixture
def sample_git_repo(tmp_path: Path) -> Path:
    """Cria um repositório git real para testes de status."""
    repo_dir = tmp_path / "meu_projeto"
    repo_dir.mkdir()

    # Inicializa git
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(repo_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Cria arquivo inicial e commita
    (repo_dir / "README.md").write_text("# Projeto Teste", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return repo_dir


def test_get_repo_details_clean(sample_git_repo: Path):
    """Valida status de repositório limpo e branch inicial."""
    info = get_repo_details(sample_git_repo)
    assert info is not None
    assert info.name == "meu_projeto"
    assert info.current_branch in ["main", "master"]
    assert info.is_dirty is False
    assert info.modified_count == 0
    assert info.untracked_count == 0
    assert "Initial commit" in info.last_commit_message


def test_get_repo_details_dirty(sample_git_repo: Path):
    """Testa detecção de arquivos modificados e não rastreados."""
    # Modifica arquivo existente
    (sample_git_repo / "README.md").write_text("# Alterado", encoding="utf-8")
    # Cria arquivo novo
    (sample_git_repo / "novo.txt").write_text("conteudo", encoding="utf-8")

    info = get_repo_details(sample_git_repo)
    assert info is not None
    assert info.is_dirty is True
    assert info.modified_count == 1
    assert info.untracked_count == 1


def test_scan_git_repositories(tmp_path: Path, sample_git_repo: Path):
    """Testa varredura de múltiplos repositórios sob a pasta raiz."""
    repos = scan_git_repositories(tmp_path)
    assert len(repos) == 1
    assert repos[0].name == "meu_projeto"
