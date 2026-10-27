"""
Testes unitários para dev.env_compare.
Valida parsing, mascaramento e auditoria diferencial entre arquivos de ambiente.
"""
import pytest
from pathlib import Path

from wintoolbox.tools.dev.env_compare.logic import (
    compare_env_files,
    generate_missing_env_snippet,
    is_sensitive_key,
    mask_value,
    parse_env_file,
)


def test_is_sensitive_key_and_mask_value():
    """Valida detecção de segredos e mascaramento."""
    assert is_sensitive_key("DATABASE_PASSWORD") is True
    assert is_sensitive_key("AWS_SECRET_ACCESS_KEY") is True
    assert is_sensitive_key("JWT_AUTH_TOKEN") is True
    assert is_sensitive_key("APP_PORT") is False

    masked = mask_value("super_secret_12345", is_secret=True)
    assert "••••" in masked
    assert "super_secret_12345" not in masked


def test_parse_env_file(tmp_path: Path):
    """Testa interpretação de comentários, aspas e exportações em .env."""
    content = """
    # Comentario global
    PORT=8080
    export DB_NAME="meu_banco"
    API_URL='https://api.local:3000' # Comentario inline
    EMPTY_VAR=
    """
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")

    parsed = parse_env_file(env_file)
    assert parsed["PORT"] == "8080"
    assert parsed["DB_NAME"] == "meu_banco"
    assert parsed["API_URL"] == "https://api.local:3000"
    assert parsed["EMPTY_VAR"] == ""


def test_compare_env_files(tmp_path: Path):
    """Testa auditoria diferencial completa com detecção de ausências e vazios."""
    template_content = """
    APP_NAME=MeuApp
    PORT=3000
    SECRET_KEY=chave_padrao
    REDIS_HOST=localhost
    """
    target_content = """
    APP_NAME=MeuAppProducao
    PORT=8080
    SECRET_KEY=
    EXTRA_CUSTOM_VAR=ativado
    """
    f_template = tmp_path / ".env.example"
    f_target = tmp_path / ".env"
    f_template.write_text(template_content, encoding="utf-8")
    f_target.write_text(target_content, encoding="utf-8")

    diffs = compare_env_files(f_template, f_target, mask_secrets=True)
    diff_map = {d.key: d for d in diffs}

    assert "REDIS_HOST" in diff_map
    assert diff_map["REDIS_HOST"].status == "missing_in_target"

    assert "SECRET_KEY" in diff_map
    assert diff_map["SECRET_KEY"].status == "empty_in_target"

    assert "EXTRA_CUSTOM_VAR" in diff_map
    assert diff_map["EXTRA_CUSTOM_VAR"].status == "missing_in_template"

    assert "PORT" in diff_map
    assert diff_map["PORT"].status == "matched"

    # Testa geração do snippet de variáveis faltantes
    snippet = generate_missing_env_snippet(diffs)
    assert "REDIS_HOST=localhost" in snippet
