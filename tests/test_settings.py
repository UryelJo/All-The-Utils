"""
Testes unitários de persistência de configurações, backup e favoritos.
Totalmente isolado com tmp_path para não poluir o ambiente do usuário.
"""
import json
from pathlib import Path
import pytest

from wintoolbox.core.settings import (
    export_settings, get_all_api_tokens, get_api_token, import_settings,
    is_favorite, load_settings, save_settings, set_api_token, toggle_favorite
)


@pytest.fixture(autouse=True)
def isolate_settings_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Garante que nenhum teste de configurações toque nos arquivos reais do usuário."""
    monkeypatch.setattr("wintoolbox.core.settings.get_settings_dir", lambda: tmp_path)
    return tmp_path


def test_settings_save_and_load(tmp_path: Path):
    st = load_settings()
    st["default_output_mode"] = "custom"
    save_settings(st)

    st2 = load_settings()
    assert st2["default_output_mode"] == "custom"
    
    # Valida integridade do arquivo gerado em disco
    saved_file = tmp_path / "settings.json"
    assert saved_file.is_file()
    disk_data = json.loads(saved_file.read_text(encoding="utf-8"))
    assert disk_data["default_output_mode"] == "custom"


def test_favorites_toggle():
    tool_id = "test.dummy_tool"
    assert is_favorite(tool_id) is False

    # Ativa
    new_state = toggle_favorite(tool_id)
    assert new_state is True
    assert is_favorite(tool_id) is True

    # Desativa
    new_state2 = toggle_favorite(tool_id)
    assert new_state2 is False
    assert is_favorite(tool_id) is False


def test_export_and_import_settings(tmp_path: Path):
    backup_file = tmp_path / "backup_test.json"
    st = load_settings()
    st["default_subfolder_name"] = "teste_backup_123"
    save_settings(st)

    # Exporta
    ok_exp = export_settings(backup_file)
    assert ok_exp is True
    assert backup_file.is_file()

    # Valida conteúdo interno do JSON exportado (Black-Box Testing)
    exported_data = json.loads(backup_file.read_text(encoding="utf-8"))
    assert exported_data["default_subfolder_name"] == "teste_backup_123"

    # Altera atual
    st["default_subfolder_name"] = "modificado"
    save_settings(st)
    assert load_settings()["default_subfolder_name"] == "modificado"

    # Restaura
    ok_imp = import_settings(backup_file)
    assert ok_imp is True
    assert load_settings()["default_subfolder_name"] == "teste_backup_123"


def test_api_tokens_management():
    # Consulta de chave inexistente deve retornar string vazia
    assert get_api_token("chave_inexistente") == ""

    set_api_token("virustotal", "token_vt_123456")
    assert get_api_token("virustotal") == "token_vt_123456"

    # Case-insensitive
    set_api_token("OPENAI", "sk-teste-999")
    assert get_api_token("openai") == "sk-teste-999"

    all_toks = get_all_api_tokens()
    assert all_toks.get("virustotal") == "token_vt_123456"
    assert all_toks.get("openai") == "sk-teste-999"

    # Remover passando vazio
    set_api_token("virustotal", "")
    assert get_api_token("virustotal") == ""
