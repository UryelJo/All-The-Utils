"""
Testes unitários para ferramentas de automação e produtividade (Fase 12).
"""
import os
from pathlib import Path
import pytest

from wintoolbox.tools.automation.autoclicker.logic import (
    get_cursor_position, perform_mouse_click
)
from wintoolbox.tools.automation.window_manager.logic import (
    list_open_windows, snap_window, set_window_always_on_top, set_window_transparency
)
from wintoolbox.tools.automation.script_runner.logic import (
    build_script_command, load_saved_scripts, save_scripts_list
)
from wintoolbox.tools.automation.workspace_launcher.logic import (
    load_workspaces, save_workspaces, launch_single_item, launch_workspace
)
from wintoolbox.tools.automation.folder_rules.logic import (
    match_rule, evaluate_folder_rules, load_folder_rules, save_folder_rules
)


class TestAutoClicker:
    def test_cursor_position(self):
        x, y = get_cursor_position()
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert x >= 0 and y >= 0

    def test_mouse_click_execution(self):
        # Apenas valida que não lança exceção em ambiente de teste
        try:
            perform_mouse_click(button="left", click_type="single")
        except Exception as e:
            pytest.fail(f"perform_mouse_click falhou inesperadamente: {e}")


class TestWindowManager:
    def test_list_windows(self):
        windows = list_open_windows()
        assert isinstance(windows, list)
        # No Windows sempre há pelo menos algumas janelas ativas
        if windows:
            first = windows[0]
            assert "hwnd" in first
            assert "title" in first
            assert isinstance(first["title"], str)

    def test_window_operations_with_invalid_hwnd(self):
        # Passar um HWND inválido (0) não deve quebrar a aplicação com crash
        res_top = set_window_always_on_top(0, True)
        assert res_top is False

        res_alpha = set_window_transparency(0, 80)
        assert res_alpha is False

        res_snap = snap_window(0, "left")
        assert res_snap is False


class TestScriptRunner:
    def test_build_script_command(self):
        cmd_ps = build_script_command("C:\\scripts\\test.ps1", "-verbose")
        assert "powershell.exe" in cmd_ps[0]
        assert "test.ps1" in str(cmd_ps)

        cmd_py = build_script_command("C:\\scripts\\app.py", "--port 8080")
        assert "python" in cmd_py[0].lower()
        assert "app.py" in str(cmd_py)

        cmd_bat = build_script_command("C:\\scripts\\run.bat")
        assert "cmd.exe" in cmd_bat[0]
        assert "run.bat" in str(cmd_bat)

    def test_script_entry_logic(self):
        original = load_saved_scripts()
        try:
            sample = [{"id": 999, "name": "Teste", "path": "C:\\test\\run.bat", "args": "", "work_dir": "C:\\test"}]
            save_scripts_list(sample)
            loaded = load_saved_scripts()
            assert len(loaded) >= 1
            assert any(s["name"] == "Teste" for s in loaded)
        finally:
            save_scripts_list(original)


class TestWorkspaceLauncher:
    def test_load_and_save_workspaces(self):
        original = load_workspaces()
        try:
            sample = [
                {
                    "id": "ws-test",
                    "name": "Test Env",
                    "description": "Desc",
                    "items": [
                        {"type": "url", "target": "https://example.com"}
                    ]
                }
            ]
            save_workspaces(sample)
            loaded = load_workspaces()
            assert len(loaded) == 1
            assert loaded[0]["id"] == "ws-test"
        finally:
            save_workspaces(original)

    def test_launch_single_empty(self):
        success, msg = launch_single_item("url", "")
        assert success is False
        assert "vazio" in msg


class TestFolderRules:
    def test_match_rule_extension(self, tmp_path):
        f = tmp_path / "documento.pdf"
        f.write_text("dummy")

        rule_match = {
            "condition_type": "extension",
            "condition_value": ".pdf, .docx",
            "action_type": "move",
            "destination": str(tmp_path / "dest")
        }
        assert match_rule(f, rule_match) is True

        rule_nomatch = {
            "condition_type": "extension",
            "condition_value": ".xlsx, .pptx",
            "action_type": "move",
            "destination": str(tmp_path / "dest")
        }
        assert match_rule(f, rule_nomatch) is False

    def test_match_rule_keyword(self, tmp_path):
        f = tmp_path / "nota_fiscal_2026.xml"
        f.write_text("xml")

        rule_match = {
            "condition_type": "keyword",
            "condition_value": "fiscal, fatura",
            "action_type": "move",
            "destination": str(tmp_path / "dest")
        }
        assert match_rule(f, rule_match) is True

    def test_evaluate_folder_rules_dry_run_and_execution(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        f1 = source / "backup.log"
        f1.write_text("log data")

        rules = [
            {
                "id": "r1",
                "name": "Mover logs",
                "condition_type": "extension",
                "condition_value": ".log",
                "action_type": "move",
                "destination": str(dest)
            }
        ]

        # Dry run não deve mover o arquivo físico
        actions_dry = evaluate_folder_rules(source, rules, dry_run=True)
        assert len(actions_dry) == 1
        assert "Simulação" in actions_dry[0]["message"]
        assert f1.exists()

        # Execução real
        actions_real = evaluate_folder_rules(source, rules, dry_run=False)
        assert len(actions_real) == 1
        assert actions_real[0]["success"] is True
        assert not f1.exists()
        assert (dest / "backup.log").exists()
