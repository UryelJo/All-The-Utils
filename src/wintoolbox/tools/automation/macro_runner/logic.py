"""
Lógica pura do Executor de Macros e Automação de Tarefas no Windows.
Zero dependências de bibliotecas gráficas.
"""
from dataclasses import asdict, dataclass, field
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("automation.macro_runner")

# Constantes Win32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_MAP: Dict[str, int] = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "del": 0x2E,
    "delete": 0x2E,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B
}


@dataclass
class MacroStep:
    action: str  # "CLICK", "TEXT", "HOTKEY", "WAIT", "MOVE", "SCROLL"
    params: Dict[str, Any] = field(default_factory=dict)
    pause_after_ms: int = 50

    def describe(self) -> str:
        """Gera descrição legível em português da ação."""
        act = self.action.upper()
        if act == "CLICK":
            btn = self.params.get("button", "esquerdo")
            ctype = self.params.get("click_type", "simples")
            x = self.params.get("x")
            y = self.params.get("y")
            pos_str = f"em ({x}, {y})" if x is not None and y is not None else "na posição atual"
            return f"Clique {ctype} ({btn}) {pos_str}"
        elif act == "TEXT":
            txt = self.params.get("text", "")
            preview = (txt[:25] + "...") if len(txt) > 25 else txt
            return f'Digitar texto: "{preview}"'
        elif act == "HOTKEY":
            keys = self.params.get("keys", [])
            return f"Atalho de teclado: {' + '.join(keys).upper()}"
        elif act == "WAIT":
            ms = self.params.get("duration_ms", 100)
            return f"Pausa de {ms} ms ({ms/1000.0:.2f} s)"
        elif act == "MOVE":
            x = self.params.get("x", 0)
            y = self.params.get("y", 0)
            return f"Mover cursor para ({x}, {y})"
        elif act == "SCROLL":
            amt = self.params.get("amount", 0)
            direction = "cima" if amt > 0 else "baixo"
            return f"Rolar mouse para {direction} ({abs(amt)} degraus)"
        return f"Ação: {act}"


@dataclass
class MacroDefinition:
    name: str = "Nova Macro"
    description: str = ""
    loops: int = 1
    delay_between_loops_ms: int = 500
    steps: List[MacroStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "loops": self.loops,
            "delay_between_loops_ms": self.delay_between_loops_ms,
            "steps": [asdict(s) for s in self.steps]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MacroDefinition":
        steps_raw = data.get("steps", [])
        steps = [
            MacroStep(
                action=s.get("action", "WAIT"),
                params=s.get("params", {}),
                pause_after_ms=int(s.get("pause_after_ms", 50))
            )
            for s in steps_raw
        ]
        return cls(
            name=str(data.get("name", "Macro Sem Nome")),
            description=str(data.get("description", "")),
            loops=max(1, int(data.get("loops", 1))),
            delay_between_loops_ms=max(0, int(data.get("delay_between_loops_ms", 500))),
            steps=steps
        )


def validate_macro_data(data: Any) -> Tuple[bool, str]:
    """Valida a integridade e o formato de dados de uma macro."""
    if not isinstance(data, dict):
        return False, "O conteúdo do arquivo deve ser um objeto JSON."

    if "name" not in data or not isinstance(data["name"], str):
        return False, "Campo 'name' obrigatório e deve ser texto."

    if "steps" not in data or not isinstance(data["steps"], list):
        return False, "Campo 'steps' deve ser uma lista de ações."

    valid_actions = {"CLICK", "TEXT", "HOTKEY", "WAIT", "MOVE", "SCROLL"}
    for idx, s in enumerate(data["steps"]):
        if not isinstance(s, dict):
            return False, f"O passo {idx+1} não é um objeto válido."
        action = str(s.get("action", "")).upper()
        if action not in valid_actions:
            return False, f"Ação desconhecida no passo {idx+1}: {action}"

    return True, "Estrutura válida."


def save_macro(macro: MacroDefinition, file_path: str) -> None:
    """Grava definição de macro em formato JSON no disco."""
    data = macro.to_dict()
    valid, err = validate_macro_data(data)
    if not valid:
        raise ValueError(f"Dados de macro inválidos: {err}")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_macro(file_path: str) -> MacroDefinition:
    """Lê e desserializa um arquivo de macro com validação."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid, err = validate_macro_data(data)
    if not valid:
        raise ValueError(f"Arquivo de macro inválido: {err}")

    return MacroDefinition.from_dict(data)


# Executores Win32 Nativos
def _get_user32() -> Any:
    try:
        import ctypes
        return ctypes.windll.user32
    except Exception:
        return None


def execute_step(step: MacroStep) -> None:
    """Executa individualmente um passo da macro utilizando a API Win32."""
    user32 = _get_user32()
    if not user32:
        return

    act = step.action.upper()

    if act == "MOVE":
        x = int(step.params.get("x", 0))
        y = int(step.params.get("y", 0))
        user32.SetCursorPos(x, y)

    elif act == "CLICK":
        x = step.params.get("x")
        y = step.params.get("y")
        if x is not None and y is not None:
            user32.SetCursorPos(int(x), int(y))

        btn = str(step.params.get("button", "esquerdo")).lower()
        if "dir" in btn or "right" in btn:
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif "meio" in btn or "mid" in btn:
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

        user32.mouse_event(down_flag, 0, 0, 0, 0)
        user32.mouse_event(up_flag, 0, 0, 0, 0)

        if step.params.get("click_type") in ("double", "duplo"):
            time.sleep(0.05)
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            user32.mouse_event(up_flag, 0, 0, 0, 0)

    elif act == "TEXT":
        text = str(step.params.get("text", ""))
        delay = max(0, int(step.params.get("delay_between_chars_ms", 10))) / 1000.0
        for ch in text:
            code = ord(ch)
            user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
            user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
            if delay > 0:
                time.sleep(delay)

    elif act == "HOTKEY":
        keys = step.params.get("keys", [])
        vks: List[int] = []
        for k in keys:
            k_low = str(k).lower().strip()
            if k_low in VK_MAP:
                vks.append(VK_MAP[k_low])
            elif len(k_low) == 1:
                # Teclas simples A-Z / 0-9
                vks.append(ord(k_low.upper()))

        # Pressiona teclas em ordem
        for vk in vks:
            user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.04)
        # Solta teclas em ordem inversa
        for vk in reversed(vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    elif act == "SCROLL":
        amt = int(step.params.get("amount", 0))
        # No Windows WHEEL_DELTA é 120 por tick
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amt * 120, 0)

    elif act == "WAIT":
        duration = max(0, int(step.params.get("duration_ms", 100))) / 1000.0
        time.sleep(duration)

    # Pausa configurada após a execução do passo
    if step.pause_after_ms > 0:
        time.sleep(step.pause_after_ms / 1000.0)


def run_macro(
    macro: MacroDefinition,
    is_cancelled: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[int, int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Executa a sequência completa de passos da macro com suporte a cancelamento.
    Retorna estatísticas da execução.
    """
    loops = max(1, macro.loops)
    total_steps = len(macro.steps)
    executed_steps = 0
    executed_loops = 0

    start_time = time.time()

    for loop_idx in range(1, loops + 1):
        if is_cancelled and is_cancelled():
            break

        executed_loops += 1

        for step_idx, step in enumerate(macro.steps, 1):
            if is_cancelled and is_cancelled():
                break

            if on_progress:
                on_progress(loop_idx, loops, step_idx, step.describe())

            execute_step(step)
            executed_steps += 1

        if loop_idx < loops and macro.delay_between_loops_ms > 0:
            delay = macro.delay_between_loops_ms / 1000.0
            # Pausa divisível para permitir cancelamento imediato
            steps_delay = int(delay * 20)
            for _ in range(max(1, steps_delay)):
                if is_cancelled and is_cancelled():
                    break
                time.sleep(delay / max(1, steps_delay))

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "completed": not (is_cancelled and is_cancelled()),
        "loops_completed": executed_loops,
        "steps_executed": executed_steps,
        "elapsed_seconds": elapsed
    }


def get_sample_presets() -> List[MacroDefinition]:
    """Retorna presets padrão de demonstração para os usuários."""
    return [
        MacroDefinition(
            name="Copiar Tudo e Minimizar",
            description="Seleciona todo o texto, copia para o clipboard e minimiza com Win+D",
            loops=1,
            steps=[
                MacroStep("HOTKEY", {"keys": ["ctrl", "a"]}, pause_after_ms=100),
                MacroStep("HOTKEY", {"keys": ["ctrl", "c"]}, pause_after_ms=100),
                MacroStep("HOTKEY", {"keys": ["win", "d"]}, pause_after_ms=50)
            ]
        ),
        MacroDefinition(
            name="Digitação de Teste Automática",
            description="Simula digitação de texto com pausa configurada",
            loops=1,
            steps=[
                MacroStep("TEXT", {"text": "Olá mundo! WinToolbox Automação ativa.\n", "delay_between_chars_ms": 15}, pause_after_ms=200),
                MacroStep("WAIT", {"duration_ms": 500}, pause_after_ms=50)
            ]
        ),
        MacroDefinition(
            name="Atualizar e Rolar Página",
            description="Pressiona F5 para recarregar e rola o mouse para baixo",
            loops=1,
            steps=[
                MacroStep("HOTKEY", {"keys": ["f5"]}, pause_after_ms=800),
                MacroStep("SCROLL", {"amount": -3}, pause_after_ms=200)
            ]
        )
    ]
