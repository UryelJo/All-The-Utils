"""
Testes unitários rigorosos para o Temporizador Pomodoro (productivity.pomodoro).
Validação determinística da máquina de estados, transição de ciclos e contagem regressiva.
"""
import pytest

from wintoolbox.tools.productivity.pomodoro.logic import (
    MODE_FOCUS,
    MODE_LONG_BREAK,
    MODE_SHORT_BREAK,
    PomodoroConfig,
    PomodoroManager,
)
from wintoolbox.tools.productivity.pomodoro.tool import PomodoroTool


def test_pomodoro_state_machine_cycle():
    cfg = PomodoroConfig(
        focus_minutes=25,
        short_break_minutes=5,
        long_break_minutes=15,
        long_break_interval=2,  # A cada 2 ciclos de foco vai para pausa longa
    )
    mgr = PomodoroManager(cfg)

    # Inicia em Foco
    assert mgr.mode == MODE_FOCUS
    assert mgr.remaining_seconds == 25 * 60
    assert mgr.is_running is False

    mgr.start()
    assert mgr.is_running is True

    # Avança quase até o final
    mgr.remaining_seconds = 2
    ended, msg = mgr.tick(step_seconds=1)
    assert ended is False
    assert mgr.remaining_seconds == 1
    assert mgr.total_focus_seconds == 1

    # Zera o tempo -> Conclui Foco 1 e avança para Pausa Curta
    ended, msg = mgr.tick(step_seconds=1)
    assert ended is True
    assert mgr.cycles_completed == 1
    assert mgr.mode == MODE_SHORT_BREAK
    assert mgr.remaining_seconds == 5 * 60

    # Simula conclusão da Pausa Curta -> Volta para Foco 2
    mgr.start()
    mgr.remaining_seconds = 1
    ended, msg = mgr.tick(step_seconds=1)
    assert ended is True
    assert mgr.mode == MODE_FOCUS
    assert mgr.remaining_seconds == 25 * 60

    # Simula conclusão do Foco 2 -> Como interval=2, agora deve ir para PAUSA LONGA!
    mgr.start()
    mgr.remaining_seconds = 1
    ended, msg = mgr.tick(step_seconds=1)
    assert ended is True
    assert mgr.cycles_completed == 2
    assert mgr.mode == MODE_LONG_BREAK
    assert mgr.remaining_seconds == 15 * 60


def test_pomodoro_formatting_and_progress():
    assert PomodoroManager.format_time(150) == "02:30"
    assert PomodoroManager.format_time(0) == "00:00"
    assert PomodoroManager.format_time(3600) == "60:00"

    mgr = PomodoroManager(PomodoroConfig(focus_minutes=10))
    mgr.remaining_seconds = 5 * 60  # Metade
    assert mgr.get_progress_percentage() == 0.5


def test_pomodoro_tool_ui(qtbot):
    tool = PomodoroTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Verifica elementos da UI
    assert "25:00" in view.lbl_clock.text()
    assert view.manager.is_running is False

    # Inicia pela UI
    view._toggle_run()
    assert view.manager.is_running is True
    assert view.btn_toggle.text() == "Pausar"

    # Pausa pela UI
    view._toggle_run()
    assert view.manager.is_running is False
    assert view.btn_toggle.text() == "Continuar"
