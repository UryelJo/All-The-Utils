"""
Testes unitários para a automação acionada por dispositivos removíveis.
Diretrizes Anti-Gambiarra: Validação determinística de regras e correspondência de rótulos.
"""
from wintoolbox.tools.automation.device_trigger.logic import (
    DeviceRule,
    load_device_rules_json,
    match_drive_with_rule,
    save_device_rules_json,
)


def test_match_drive_with_rule():
    rule_all = DeviceRule("r1", "Todas", "", "open_explorer", "", enabled=True)
    assert match_drive_with_rule(rule_all, "PENDRIVE_QUALQUER") is True

    rule_fotos = DeviceRule("r2", "Fotos", "FOTOS", "copy_to_folder", "C:\\Backup", enabled=True)
    assert match_drive_with_rule(rule_fotos, "MEU_PENDRIVE_FOTOS_2026") is True
    assert match_drive_with_rule(rule_fotos, "TRABALHO_DOCS") is False

    rule_disabled = DeviceRule("r3", "Desativada", "", "notify", "", enabled=False)
    assert match_drive_with_rule(rule_disabled, "QUALQUER") is False


def test_device_rules_json_serialization(tmp_path):
    p = tmp_path / "device_rules.json"
    rules = [
        DeviceRule("d1", "Regra 1", "BACKUP", "open_explorer", "C:\\", True)
    ]
    save_device_rules_json(rules, str(p))
    assert p.exists()

    loaded = load_device_rules_json(str(p))
    assert len(loaded) == 1
    assert loaded[0].id == "d1"
    assert loaded[0].volume_label_filter == "BACKUP"
