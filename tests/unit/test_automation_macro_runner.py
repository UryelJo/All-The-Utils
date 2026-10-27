"""
Testes unitários rigorosos para o Executor de Macros (automation.macro_runner).
"""
import json
import os
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from wintoolbox.tools.automation.macro_runner.logic import (
    MacroDefinition,
    MacroStep,
    get_sample_presets,
    load_macro,
    run_macro,
    save_macro,
    validate_macro_data
)
from wintoolbox.tools.automation.macro_runner.tool import (
    MacroRunnerTool,
    MacroRunnerView
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_macro_data_validation_and_schema():
    """Valida integridade estrutural e rejeição de entradas inválidas."""
    # 1. Macro válida
    valid_data = {
        "name": "Teste",
        "description": "Desc",
        "loops": 2,
        "delay_between_loops_ms": 100,
        "steps": [
            {"action": "CLICK", "params": {"button": "left"}},
            {"action": "WAIT", "params": {"duration_ms": 50}}
        ]
    }
    is_valid, msg = validate_macro_data(valid_data)
    assert is_valid is True

    # 2. Rejeição de tipos não-dicionário
    assert validate_macro_data("string")[0] is False
    assert validate_macro_data([])[0] is False

    # 3. Nome ausente ou inválido
    assert validate_macro_data({"steps": []})[0] is False

    # 4. Ação desconhecida
    invalid_action = {"name": "Ruim", "steps": [{"action": "EXPLODIR_PC"}]}
    is_valid_inv, err_msg = validate_macro_data(invalid_action)
    assert is_valid_inv is False
    assert "Ação desconhecida" in err_msg


def test_macro_file_save_and_load_blackbox(tmp_path):
    """
    Princípio da Validação do Efeito Real:
    Salva uma macro no disco, inspeciona o JSON físico e recarrega.
    """
    file_path = tmp_path / "minha_macro.json"

    original_macro = MacroDefinition(
        name="Macro Blackbox",
        description="Teste de integridade física no disco",
        loops=3,
        delay_between_loops_ms=250,
        steps=[
            MacroStep("CLICK", {"button": "right", "x": 100, "y": 200}, pause_after_ms=50),
            MacroStep("TEXT", {"text": "WinToolbox 2026", "delay_between_chars_ms": 5}, pause_after_ms=100),
            MacroStep("HOTKEY", {"keys": ["ctrl", "s"]}, pause_after_ms=30)
        ]
    )

    # Gravação no disco
    save_macro(original_macro, str(file_path))
    assert os.path.exists(file_path)

    # Leitura bruta do arquivo JSON
    with open(file_path, "r", encoding="utf-8") as f:
        disk_json = json.load(f)

    assert disk_json["name"] == "Macro Blackbox"
    assert disk_json["loops"] == 3
    assert len(disk_json["steps"]) == 3
    assert disk_json["steps"][0]["action"] == "CLICK"
    assert disk_json["steps"][0]["params"]["x"] == 100
    assert disk_json["steps"][1]["params"]["text"] == "WinToolbox 2026"
    assert disk_json["steps"][2]["params"]["keys"] == ["ctrl", "s"]

    # Carregamento pela função oficial
    loaded = load_macro(str(file_path))
    assert loaded.name == original_macro.name
    assert loaded.description == original_macro.description
    assert loaded.loops == original_macro.loops
    assert len(loaded.steps) == 3
    assert loaded.steps[0].describe() == "Clique simples (right) em (100, 200)"
    assert loaded.steps[1].describe() == 'Digitar texto: "WinToolbox 2026"'
    assert loaded.steps[2].describe() == "Atalho de teclado: CTRL + S"


@patch("wintoolbox.tools.automation.macro_runner.logic._get_user32")
def test_macro_execution_with_isolation(mock_user32):
    """Valida execução completa da sequência isolando chamadas Win32 do sistema real."""
    fake_user32 = MagicMock()
    mock_user32.return_value = fake_user32

    macro = MacroDefinition(
        name="Macro Simulação",
        loops=2,
        delay_between_loops_ms=10,
        steps=[
            MacroStep("MOVE", {"x": 500, "y": 300}, pause_after_ms=0),
            MacroStep("CLICK", {"button": "left", "click_type": "single"}, pause_after_ms=0),
            MacroStep("TEXT", {"text": "OK", "delay_between_chars_ms": 0}, pause_after_ms=0)
        ]
    )

    result = run_macro(macro)
    assert result["success"] is True
    assert result["completed"] is True
    assert result["loops_completed"] == 2
    assert result["steps_executed"] == 6  # 3 passos x 2 repetições

    # Verifica se as APIs nativas do Windows foram acionadas
    assert fake_user32.SetCursorPos.call_count >= 2
    assert fake_user32.mouse_event.call_count >= 4  # down + up x 2
    assert fake_user32.keybd_event.call_count >= 8  # 2 chars * (down + up) * 2 loops


@patch("wintoolbox.tools.automation.macro_runner.logic._get_user32")
def test_macro_execution_cancellation(mock_user32):
    """Valida interrupção imediata quando a flag de cancelamento é disparada."""
    fake_user32 = MagicMock()
    mock_user32.return_value = fake_user32

    macro = MacroDefinition(
        name="Macro Longa",
        loops=10,
        steps=[MacroStep("WAIT", {"duration_ms": 10}, pause_after_ms=0)]
    )

    call_count = [0]

    def cancel_after_first():
        call_count[0] += 1
        return call_count[0] > 1

    result = run_macro(macro, is_cancelled=cancel_after_first)
    assert result["completed"] is False
    assert result["loops_completed"] == 1


def test_macro_runner_view(qapp):
    """Valida criação, edição visual de passos e reordenação na UI."""
    tool = MacroRunnerTool()
    view = MacroRunnerView(tool)

    # 1. Limpar passos existentes
    view._clear_all_steps()
    assert len(view._macro.steps) == 0
    assert view.table_steps.rowCount() == 0

    # 2. Adicionar Passo: TEXTO
    idx_text = view.combo_action.findData("TEXT")
    assert idx_text >= 0
    view.combo_action.setCurrentIndex(idx_text)
    view.txt_input_text.setText("Teste de Digitação")
    view.spin_step_pause.setValue(200)
    view._add_step()

    assert len(view._macro.steps) == 1
    assert view.table_steps.rowCount() == 1
    assert view._macro.steps[0].action == "TEXT"
    assert view._macro.steps[0].params["text"] == "Teste de Digitação"
    assert view._macro.steps[0].pause_after_ms == 200

    # 3. Adicionar Passo: HOTKEY
    idx_hotkey = view.combo_action.findData("HOTKEY")
    assert idx_hotkey >= 0
    view.combo_action.setCurrentIndex(idx_hotkey)
    view.txt_hotkey.setText("ctrl+v")
    view._add_step()

    assert len(view._macro.steps) == 2
    assert view.table_steps.rowCount() == 2

    # 4. Mover Passo 2 para Cima
    view.table_steps.setCurrentCell(1, 0)
    view._move_step_up()
    assert view._macro.steps[0].action == "HOTKEY"
    assert view._macro.steps[1].action == "TEXT"

    # 5. Duplicar Passo
    view.table_steps.setCurrentCell(0, 0)
    view._duplicate_step()
    assert len(view._macro.steps) == 3
    assert view.table_steps.rowCount() == 3

    # 6. Remover Passo
    view.table_steps.setCurrentCell(0, 0)
    view._remove_step()
    assert len(view._macro.steps) == 2
    assert view.table_steps.rowCount() == 2
