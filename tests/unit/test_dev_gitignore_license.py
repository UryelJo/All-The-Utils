"""
Testes unitários para dev.gitignore_license.
Valida composição de regras de exclusão git e preenchimento de licenças open-source.
"""
from wintoolbox.tools.dev.gitignore_license.logic import (
    compose_gitignore,
    generate_license,
)


def test_compose_gitignore():
    """Valida junção de seções de templates com cabeçalhos organizados."""
    composed = compose_gitignore(["Python", "Node.js"], custom_rules="*.custom_secret\ncache/")
    assert "# === Python ===" in composed or "# Python" in composed
    assert "__pycache__/" in composed
    assert "node_modules/" in composed
    assert "*.custom_secret" in composed
    assert "# Regras Personalizadas" in composed


def test_generate_license_mit():
    """Valida preenchimento de ano e detentor dos direitos na licença MIT."""
    lic = generate_license("MIT", year=2026, holder="Empresa XYZ")
    assert "MIT License" in lic
    assert "Copyright (c) 2026 Empresa XYZ" in lic


def test_generate_license_apache():
    """Valida geração de licença Apache 2.0."""
    lic = generate_license("Apache-2.0", year=2025, holder="Fulano de Tal")
    assert "Apache License" in lic
    assert "Version 2.0" in lic
    assert "Copyright 2025 Fulano de Tal" in lic


def test_generate_license_unlicense():
    """Valida modelo de domínio público The Unlicense."""
    lic = generate_license("Unlicense")
    assert "free and unencumbered software released into the public domain" in lic
