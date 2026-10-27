"""
Testes unitários para regras automáticas de posicionamento de janelas.
Diretrizes Anti-Gambiarra: Validação determinística de geometria espacial e filtros.
"""
from wintoolbox.tools.automation.window_rules.logic import (
    WindowRule,
    calculate_window_coordinates,
    load_window_rules_json,
    match_window_with_rule,
    save_window_rules_json,
)


def test_match_window_with_rule():
    rule = WindowRule(
        id="w1",
        name="VS Code",
        process_name="code.exe",
        title_contains="WinToolbox",
        target_monitor=0,
        window_state="maximized",
        enabled=True
    )

    assert match_window_with_rule(rule, "WinToolbox - Visual Studio Code", "Code.exe") is True
    assert match_window_with_rule(rule, "OutroProjeto - Visual Studio Code", "Code.exe") is False
    assert match_window_with_rule(rule, "WinToolbox - Chrome", "chrome.exe") is False


def test_calculate_window_coordinates():
    # Monitor Full HD: left=0, top=0, right=1920, bottom=1080
    mon = (0, 0, 1920, 1080)

    r_max = WindowRule("r1", "Max", "app.exe", "", 0, "maximized")
    assert calculate_window_coordinates(mon, r_max) == (0, 0, 1920, 1080)

    r_snap_l = WindowRule("r2", "SnapL", "app.exe", "", 0, "snap_left")
    assert calculate_window_coordinates(mon, r_snap_l) == (0, 0, 960, 1080)

    r_snap_r = WindowRule("r3", "SnapR", "app.exe", "", 0, "snap_right")
    assert calculate_window_coordinates(mon, r_snap_r) == (960, 0, 960, 1080)

    r_normal = WindowRule("r4", "Norm", "app.exe", "", 0, "normal", x=50, y=50, width=800, height=600)
    assert calculate_window_coordinates(mon, r_normal) == (50, 50, 800, 600)


def test_window_rules_json_serialization(tmp_path):
    p = tmp_path / "win_rules.json"
    rules = [
        WindowRule("wr1", "Regra 1", "slack.exe", "", 1, "snap_left", enabled=True)
    ]
    save_window_rules_json(rules, str(p))
    assert p.exists()

    loaded = load_window_rules_json(str(p))
    assert len(loaded) == 1
    assert loaded[0].id == "wr1"
    assert loaded[0].process_name == "slack.exe"
    assert loaded[0].window_state == "snap_left"
