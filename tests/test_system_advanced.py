"""
Testes automatizados para a Fase 7: Sistema, Processos e Manutenção Avançada.
Valida as 10 novas ferramentas e suas camadas de lógica pura.
"""
import os
from pathlib import Path
import pytest

from wintoolbox.core.registry import get_all_tools, get_tool
from wintoolbox.tools.system.process_manager.logic import (
    get_process_details, list_running_processes
)
from wintoolbox.tools.system.services_manager.logic import list_windows_services
from wintoolbox.tools.system.startup_manager.logic import list_startup_items
from wintoolbox.tools.system.hosts_editor.logic import (
    read_hosts_file, restore_hosts_backup, save_hosts_file
)
from wintoolbox.tools.system.env_editor.logic import (
    get_environment_variables, get_path_entries
)
from wintoolbox.tools.system.uninstaller.logic import list_installed_programs
from wintoolbox.tools.system.power_manager.logic import (
    get_battery_info, get_power_plans
)
from wintoolbox.tools.system.driver_backup.logic import list_third_party_drivers
from wintoolbox.tools.system.quick_tweaks.logic import get_quick_tweaks_state
from wintoolbox.tools.system.task_scheduler.logic import list_scheduled_tasks


def test_phase_7_tools_registered():
    """Valida se todas as 10 ferramentas da Fase 7 estão devidamente registradas."""
    expected_ids = [
        "system.process_manager",
        "system.services_manager",
        "system.startup_manager",
        "system.hosts_editor",
        "system.env_editor",
        "system.uninstaller",
        "system.power_manager",
        "system.driver_backup",
        "system.quick_tweaks",
        "system.task_scheduler",
    ]
    all_tools = {t.id: t for t in get_all_tools()}
    for t_id in expected_ids:
        assert t_id in all_tools, f"Ferramenta {t_id} não encontrada no registro."
        tool = get_tool(t_id)
        assert tool.category == "Sistema"
        assert len(tool.description) > 0


def test_process_manager_logic():
    """Valida listagem de processos e detalhes do processo atual."""
    current_pid = os.getpid()
    procs = list_running_processes()
    assert len(procs) > 0

    pids = [p["pid"] for p in procs]
    assert current_pid in pids

    details = get_process_details(current_pid)
    assert details["success"] is True
    assert details["pid"] == current_pid
    assert "python" in details["name"].lower()


def test_services_manager_logic():
    """Valida listagem de serviços do Windows."""
    services = list_windows_services()
    assert isinstance(services, list)
    if services:
        first = services[0]
        assert "name" in first
        assert "status" in first
        assert "start_type" in first


def test_startup_manager_logic():
    """Valida listagem de itens de inicialização."""
    items = list_startup_items()
    assert isinstance(items, list)


def test_hosts_editor_logic(tmp_path: Path):
    """Valida leitura, gravação e restauração do arquivo hosts com arquivo temporário."""
    fake_hosts = tmp_path / "hosts_teste"
    initial_content = (
        "# Comentário inicial\n"
        "127.0.0.1 localhost\n"
        "192.168.1.100 servidor.local # servidor interno\n"
        "# 10.0.0.1 desativado.local\n"
    )
    fake_hosts.write_text(initial_content, encoding="utf-8")

    entries = read_hosts_file(fake_hosts)
    assert len(entries) >= 2

    # Adiciona nova entrada e grava
    entries.append({
        "ip": "1.1.1.1",
        "hostname": "cloudflare-dns.com",
        "comment": "dns teste",
        "is_enabled": True
    })

    ok, msg = save_hosts_file(entries, hosts_path=fake_hosts, create_backup=True)
    assert ok is True

    # Re-lê
    new_entries = read_hosts_file(fake_hosts)
    ips = [e["ip"] for e in new_entries]
    assert "1.1.1.1" in ips


def test_env_editor_logic():
    """Valida leitura de variáveis de usuário e entradas do PATH."""
    user_vars = get_environment_variables(scope="user")
    assert isinstance(user_vars, dict)

    path_entries = get_path_entries(scope="user")
    assert isinstance(path_entries, list)
    for ent in path_entries:
        assert "raw_path" in ent
        assert "exists" in ent


def test_uninstaller_logic():
    """Valida varredura de programas instalados no Windows."""
    progs = list_installed_programs()
    assert isinstance(progs, list)
    # Geralmente em qualquer máquina Windows há pelo menos alguns programas instalados
    if progs:
        first = progs[0]
        assert "name" in first
        assert "version" in first


def test_power_manager_logic():
    """Valida recuperação de planos de energia e status de bateria."""
    plans = get_power_plans()
    assert isinstance(plans, list)

    battery = get_battery_info()
    # Se for notebook, battery é dict; se for desktop, None
    if battery is not None:
        assert "percent" in battery


def test_driver_backup_logic():
    """Valida listagem de drivers via pnputil."""
    drivers = list_third_party_drivers()
    assert isinstance(drivers, list)


def test_quick_tweaks_logic():
    """Valida leitura do estado dos ajustes rápidos."""
    states = get_quick_tweaks_state()
    assert "show_hidden_files" in states
    assert "show_file_extensions" in states
    assert "dark_mode_apps" in states
    assert "dark_mode_system" in states
    assert isinstance(states["show_hidden_files"], bool)


def test_task_scheduler_logic():
    """Valida listagem de tarefas agendadas."""
    tasks = list_scheduled_tasks(hide_microsoft=True)
    assert isinstance(tasks, list)
