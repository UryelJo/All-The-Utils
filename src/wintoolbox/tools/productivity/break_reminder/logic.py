"""
Lógica pura para o assistente de ergonomia e pausas ativas (regra 20-20-20, alongamento e hidratação).
Isolada de qualquer framework de interface gráfica.
"""
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ReminderProfile:
    name: str = "Padrão Escritório"
    eye_interval_min: int = 20        # Regra 20-20-20: a cada 20 min
    eye_duration_sec: int = 20        # Olhar para longe por 20 segundos
    stretch_interval_min: int = 45    # Alongamento a cada 45 min
    stretch_duration_sec: int = 60    # 1 minuto de alongamento
    water_interval_min: int = 60      # Hidratação a cada 60 min
    eye_enabled: bool = True
    stretch_enabled: bool = True
    water_enabled: bool = True
    sound_alert: bool = True


ERGONOMIC_TIPS = {
    "eye": [
        "Regra 20-20-20: Olhe para um ponto a pelo menos 6 metros de distância por 20 segundos.",
        "Pisque intencionalmente várias vezes para lubrificar a superfície ocular.",
        "Feche os olhos suavemente e cubra-os com as palmas das mãos aquecidas por alguns instantes.",
        "Ajuste o brilho do monitor para não ficar muito mais claro ou escuro que a iluminação da sala."
    ],
    "stretch": [
        "Incline a cabeça suavemente para cada ombro por 15 segundos para relaxar o trapézio.",
        "Gire os ombros para trás 10 vezes em movimentos circulares amplos.",
        "Entrelace os dedos e estenda os braços para cima, alongando a coluna dorsal.",
        "Levante-se da cadeira e dê alguns passos para reativar o retorno venoso nas pernas."
    ],
    "water": [
        "Beba um copo de água (250 ml) para manter a hidratação e o foco cerebral.",
        "A hidratação constante reduz a fadiga mental e dores de cabeça tensionais.",
        "Aproveite a ida para buscar água para movimentar as pernas e mudar de postura."
    ]
}


def get_random_tip(reminder_type: str, index: int = 0) -> str:
    """Retorna uma dica ergonômica com base no tipo de lembrete."""
    tips = ERGONOMIC_TIPS.get(reminder_type, ERGONOMIC_TIPS["stretch"])
    return tips[index % len(tips)]


def format_countdown(seconds: int) -> str:
    """Formata segundos em MM:SS ou HH:MM:SS."""
    if seconds < 0:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def save_reminder_profile(profile: ReminderProfile, path: Path) -> None:
    """Salva configurações do perfil ergonômico no disco."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, ensure_ascii=False, indent=2)


def load_reminder_profile(path: Path) -> ReminderProfile:
    """Carrega perfil ergonômico do disco."""
    path = Path(path).resolve()
    if not path.is_file():
        return ReminderProfile()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ReminderProfile(**data)
