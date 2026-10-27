"""
Testes unitários para o gerenciamento de atalhos globais de teclado.
Diretrizes Anti-Gambiarra: Validação determinística de modificadores e códigos virtuais de teclas.
"""
from wintoolbox.tools.automation.hotkeys.logic import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    GlobalHotkey,
    load_hotkeys_json,
    parse_hotkey_string,
    save_hotkeys_json,
    validate_hotkey_syntax,
)


def test_parse_hotkey_string():
    # Ctrl+Alt+K
    mods, vk = parse_hotkey_string("Ctrl+Alt+K")
    assert mods == (MOD_CONTROL | MOD_ALT)
    assert vk == 0x4B  # 'K'

    # Shift+F5
    mods_f5, vk_f5 = parse_hotkey_string("Shift+F5")
    assert mods_f5 == MOD_SHIFT
    assert vk_f5 == 0x74  # F5


def test_validate_hotkey_syntax():
    assert validate_hotkey_syntax("Ctrl+Alt+A") is True
    assert validate_hotkey_syntax("Win+Shift+Z") is True
    assert validate_hotkey_syntax("TecladoInexistenteXYZ") is False
    assert validate_hotkey_syntax("") is False


def test_hotkeys_json_serialization(tmp_path):
    p = tmp_path / "hotkeys.json"
    hotkeys = [
        GlobalHotkey("h1", "Test", "Ctrl+Alt+T", "open_tool", "calc.finance", True)
    ]
    save_hotkeys_json(hotkeys, str(p))
    assert p.exists()

    loaded = load_hotkeys_json(str(p))
    assert len(loaded) == 1
    assert loaded[0].id == "h1"
    assert loaded[0].key_combination == "Ctrl+Alt+T"
    assert loaded[0].target == "calc.finance"
