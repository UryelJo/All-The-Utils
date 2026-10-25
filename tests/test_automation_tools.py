"""
Testes unitários para ferramentas de automação e produtividade (Fase 12).
Validação determinística, isolamento de dados com tmp_path e captura de eventos win32.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.automation.autoclicker.logic import (
    get_cursor_position, perform_mouse_click,
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
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


@pytest.fixture(autouse=True)
def isolate_automation_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Garante que a persistência de scripts e workspaces fique isolada em tmp_path."""
    monkeypatch.setattr("wintoolbox.core.settings.get_app_dir", lambda: tmp_path)
    monkeypatch.setattr("wintoolbox.core.settings.get_settings_dir", lambda: tmp_path)
    return tmp_path


class TestAutoClicker:
    def test_cursor_position(self):
        x, y = get_cursor_position()
        assert isinstance(x, int)
        assert isinstance(y, int)

    def test_mouse_click_execution_intercepted(self, monkeypatch: pytest.MonkeyPatch):
        """Valida envio das flags Win32 corretas sem disparar cliques físicos na tela."""
        recorded_events = []

        def fake_mouse_event(flags, dx, dy, data, extra_info):
            recorded_events.append(flags)

        import ctypes
        monkeypatch.setattr(ctypes.windll.user32, "mouse_event", fake_mouse_event)

        # Clique esquerdo simples
        perform_mouse_click(button="left", click_type="single")
        assert recorded_events == [MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP]

        # Clique direito simples
        recorded_events.clear()
        perform_mouse_click(button="right", click_type="single")
        assert recorded_events == [MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP]


class TestWindowManager:
    def test_list_windows(self):
        windows = list_open_windows()
        assert isinstance(windows, list)
        for w in windows:
            assert "hwnd" in w
            assert "title" in w
            assert "is_topmost" in w
            assert isinstance(w["hwnd"], int)
            assert isinstance(w["title"], str)
            assert isinstance(w["is_topmost"], bool)

    def test_window_operations_with_invalid_hwnd(self):
        # Passar um HWND inválido (0) deve retornar False de forma segura
        assert set_window_always_on_top(0, True) is False
        assert set_window_transparency(0, 80) is False
        assert snap_window(0, "left") is False


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

    def test_script_entry_logic_isolated(self):
        assert len(load_saved_scripts()) == 0

        sample = [{"id": 999, "name": "Teste Script", "path": "C:\\test\\run.bat", "args": "", "work_dir": "C:\\test"}]
        save_scripts_list(sample)

        loaded = load_saved_scripts()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "Teste Script"
        assert loaded[0]["id"] == 999


class TestWorkspaceLauncher:
    def test_load_and_save_workspaces_isolated(self):
        # Quando não há arquivo salvo em disco, retorna os 2 workspaces padrão do sistema
        defaults = load_workspaces()
        assert len(defaults) == 2
        assert defaults[0]["id"] == "dev_web"
        assert defaults[1]["id"] == "estudos"

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
        f1.write_text("log data confidencial", encoding="utf-8")

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
        assert f1.is_file()

        # Execução real com Validação do Efeito Real (leitura no destino)
        actions_real = evaluate_folder_rules(source, rules, dry_run=False)
        assert len(actions_real) == 1
        assert actions_real[0]["success"] is True
        assert not f1.exists()

        moved_dest = dest / "backup.log"
        assert moved_dest.is_file()
        assert moved_dest.read_text(encoding="utf-8") == "log data confidencial"
