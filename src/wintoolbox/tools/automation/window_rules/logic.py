"""
Lógica pura para regras automáticas de posicionamento, monitor e estado de janelas no Windows.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class WindowRule:
    """Regra de posicionamento automático para janelas de aplicativos."""
    id: str
    name: str
    process_name: str        # Ex: "code.exe", "slack.exe", "spotify.exe"
    title_contains: str      # Substring no título da janela
    target_monitor: int      # 0 = Principal, 1 = Secundário
    window_state: str        # "normal", "maximized", "snap_left", "snap_right"
    x: int = 100
    y: int = 100
    width: int = 1200
    height: int = 800
    enabled: bool = True


def match_window_with_rule(rule: WindowRule, window_title: str, process_name: str) -> bool:
    """
    Verifica se uma janela corresponde aos critérios da regra.
    """
    if not rule.enabled:
        return False

    if rule.process_name:
        if rule.process_name.lower() not in process_name.lower():
            return False

    if rule.title_contains:
        if rule.title_contains.lower() not in window_title.lower():
            return False

    return True


def calculate_window_coordinates(
    monitor_rect: Tuple[int, int, int, int],
    rule: WindowRule
) -> Tuple[int, int, int, int]:
    """
    Calcula as coordenadas finais (x, y, w, h) respeitando o retângulo do monitor selecionado.
    monitor_rect: (left, top, right, bottom)
    """
    m_left, m_top, m_right, m_bottom = monitor_rect
    m_width = m_right - m_left
    m_height = m_bottom - m_top

    if rule.window_state == "maximized":
        return m_left, m_top, m_width, m_height
    elif rule.window_state == "snap_left":
        return m_left, m_top, m_width // 2, m_height
    elif rule.window_state == "snap_right":
        return m_left + (m_width // 2), m_top, m_width // 2, m_height

    # Modo normal com coordenadas relativas ao monitor
    x = m_left + max(0, rule.x)
    y = m_top + max(0, rule.y)
    w = min(m_width, max(200, rule.width))
    h = min(m_height, max(200, rule.height))

    return x, y, w, h


def save_window_rules_json(rules: List[WindowRule], filepath: str) -> None:
    """Salva a lista de regras de janelas em JSON."""
    raw = [asdict(r) for r in rules]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def load_window_rules_json(filepath: str) -> List[WindowRule]:
    """Carrega regras de janelas a partir de arquivo JSON."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return [
                WindowRule(
                    id=d.get("id", ""),
                    name=d.get("name", "Regra de Janela"),
                    process_name=d.get("process_name", ""),
                    title_contains=d.get("title_contains", ""),
                    target_monitor=int(d.get("target_monitor", 0)),
                    window_state=d.get("window_state", "normal"),
                    x=int(d.get("x", 100)),
                    y=int(d.get("y", 100)),
                    width=int(d.get("width", 1200)),
                    height=int(d.get("height", 800)),
                    enabled=d.get("enabled", True)
                )
                for d in raw if isinstance(d, dict)
            ]
    except Exception:
        return []
