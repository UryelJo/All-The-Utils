"""
Testes de validação de efeito real para system.keep_awake.logic.
"""
import sys
import pytest

from wintoolbox.tools.system.keep_awake.logic import (
    ES_CONTINUOUS,
    ES_DISPLAY_REQUIRED,
    ES_SYSTEM_REQUIRED,
    calculate_execution_flags,
    format_remaining_seconds,
    apply_keep_awake,
    release_keep_awake,
)


def test_calculate_execution_flags_deterministic():
    # Tela e Sistema
    both = calculate_execution_flags(keep_display=True, keep_system=True)
    expected_both = ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
    assert both == expected_both
    assert both == 0x80000003

    # Somente Sistema (tela pode apagar)
    sys_only = calculate_execution_flags(keep_display=False, keep_system=True)
    assert sys_only == (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    assert sys_only == 0x80000001

    # Somente Tela
    disp_only = calculate_execution_flags(keep_display=True, keep_system=False)
    assert disp_only == (ES_CONTINUOUS | ES_DISPLAY_REQUIRED)
    assert disp_only == 0x80000002


def test_format_remaining_seconds_deterministic():
    assert format_remaining_seconds(3665) == "01:01:05"
    assert format_remaining_seconds(60) == "00:01:00"
    assert format_remaining_seconds(0) == "00:00:00"
    assert format_remaining_seconds(-10) == "00:00:00"


@pytest.mark.skipif(sys.platform != "win32", reason="Requer API do Windows SetThreadExecutionState")
def test_apply_and_release_keep_awake_real_effect():
    # Validação do Efeito Real: aplica o estado e comprova retorno positivo da API do kernel
    activated = apply_keep_awake(keep_display=True, keep_system=True)
    assert activated is True

    # Restaura o estado normal de energia
    released = release_keep_awake()
    assert released is True
