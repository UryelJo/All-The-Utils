"""
Testes unitários de persistência de configurações, backup e favoritos.
"""
from pathlib import Path
from wintoolbox.core.settings import (
    export_settings, import_settings, is_favorite, load_settings,
    save_settings, toggle_favorite
)

def test_settings_save_and_load():
    st = load_settings()
    st["default_output_mode"] = "custom"
    save_settings(st)

    st2 = load_settings()
    assert st2["default_output_mode"] == "custom"

def test_favorites_toggle():
    tool_id = "test.dummy_tool"
    # Inicialmente falso
    if is_favorite(tool_id):
        toggle_favorite(tool_id)

    assert not is_favorite(tool_id)

    # Ativa
    new_state = toggle_favorite(tool_id)
    assert new_state is True
    assert is_favorite(tool_id)

    # Desativa
    new_state2 = toggle_favorite(tool_id)
    assert new_state2 is False
    assert not is_favorite(tool_id)

def test_export_and_import_settings(tmp_path: Path):
    backup_file = tmp_path / "backup_test.json"
    st = load_settings()
    st["default_subfolder_name"] = "teste_backup_123"
    save_settings(st)

    # Exporta
    ok_exp = export_settings(backup_file)
    assert ok_exp is True
    assert backup_file.exists()

    # Altera atual
    st["default_subfolder_name"] = "modificado"
    save_settings(st)
    assert load_settings()["default_subfolder_name"] == "modificado"

    # Restaura
    ok_imp = import_settings(backup_file)
    assert ok_imp is True
    assert load_settings()["default_subfolder_name"] == "teste_backup_123"
