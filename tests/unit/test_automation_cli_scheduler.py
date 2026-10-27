"""
Testes unitários para a integração do agendador com schtasks.exe.
Diretrizes Anti-Gambiarra: Validação determinística da linha de comando gerada.
"""
from wintoolbox.tools.automation.cli_scheduler.logic import (
    ScheduledTask,
    build_schtasks_create_command,
    build_schtasks_delete_command,
    load_scheduled_tasks_json,
    save_scheduled_tasks_json,
)


def test_build_schtasks_create_command():
    cmd = build_schtasks_create_command(
        task_name="Limpeza",
        python_exe="C:\\Python\\python.exe",
        main_script_path="C:\\WinToolbox\\main.py",
        tool_id="system.temp_cleaner",
        frequency="DAILY",
        time_str="03:00"
    )

    assert cmd[0] == "schtasks"
    assert cmd[1] == "/Create"
    assert "/TN" in cmd
    assert "WinToolbox_Limpeza" in cmd
    assert "/SC" in cmd
    assert "DAILY" in cmd
    assert "/ST" in cmd
    assert "03:00" in cmd


def test_build_schtasks_delete_command():
    cmd = build_schtasks_delete_command("Limpeza")
    assert cmd == ["schtasks", "/Delete", "/TN", "WinToolbox_Limpeza", "/F"]


def test_scheduled_tasks_json_serialization(tmp_path):
    p = tmp_path / "tasks.json"
    tasks = [
        ScheduledTask("Task1", "tool.one", "", "WEEKLY", "12:00", True)
    ]
    save_scheduled_tasks_json(tasks, str(p))
    assert p.exists()

    loaded = load_scheduled_tasks_json(str(p))
    assert len(loaded) == 1
    assert loaded[0].task_name == "Task1"
    assert loaded[0].tool_id == "tool.one"
    assert loaded[0].frequency == "WEEKLY"
